"""Compress the paper PDF for the website, keeping text as vectors."""

import io
import os

import pymupdf
from PIL import Image

SRC = r"media/ArgusPaper11_24_26.pdf"
DST = r"ArgusPaper/root.pdf"

# xref -> (target dpi, jpeg quality). Photos first, then line plots.
RASTER = {
    69: (280, 84),
    15: (300, 86),
    2: (280, 84),
    26: (320, 90),
    28: (320, 90),
}
VECTOR_DPI = 320
VECTOR_QUALITY = 88


def to_jpeg(im, quality):
    if im.mode != "RGB":
        im = im.convert("RGB")
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True, subsampling=0)
    return buf.getvalue()


def scaled_image(doc, xref, dpi_now, dpi_target):
    pix = pymupdf.Pixmap(doc, xref)
    if pix.n == 4:
        mode = "RGBA"
    elif pix.n == 3:
        mode = "RGB"
    elif pix.n == 1:
        mode = "L"
    else:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        mode = "RGB"
    im = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    scale = min(1.0, dpi_target / dpi_now)
    if scale < 0.99:
        nw = max(1, round(im.width * scale))
        nh = max(1, round(im.height * scale))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    return im


def form_jpeg(doc):
    """Rasterize the embedded joint-error plot. The page draws it as a form."""
    page = None
    for candidate in doc:
        if "/Im10 Do" in candidate.read_contents().decode("latin1"):
            page = candidate
            break
    if page is None:
        raise SystemExit("joint RMSE figure was not found")
    raw = page.read_contents().decode("latin1")
    idx = raw.find("/Im10 Do")
    chunk = raw[max(0, idx - 220):idx]
    mats = []
    for a, _d, e, f in __import__("re").findall(
        r"([0-9.]+)\s+0\s+0\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+cm", chunk
    ):
        mats.append((float(a), float(e), float(f)))
    scale, tx, ty = 1.0, 0.0, 0.0
    for a, e, f in mats:
        if abs(a - 1) < 1e-6 and (e or f):
            tx, ty = e, f
        elif abs(a - 1) > 1e-6:
            scale = a
    form_xref = None
    for xref in range(1, doc.xref_length()):
        obj = doc.xref_object(xref)
        if "joint_rmse_sliding_10s_wide.pdf" in obj:
            form_xref = xref
            break
    bbox_vals = [float(v) for v in doc.xref_get_key(form_xref, "BBox")[1].strip("[]").split()]
    bbox = pymupdf.Rect(bbox_vals)
    disp_w = bbox.width * scale
    disp_h = bbox.height * scale
    clip = pymupdf.Rect(tx, page.rect.height - (ty + disp_h), tx + disp_w, page.rect.height - ty)
    pix = page.get_pixmap(clip=clip, dpi=VECTOR_DPI, alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return to_jpeg(im, VECTOR_QUALITY), im.size, form_xref, bbox


def main():
    doc = pymupdf.open(SRC)
    jpeg, fig_size, form_xref, form_bbox = form_jpeg(doc)
    print(f"vector figure: {fig_size} {len(jpeg)/1024:.0f} KB")

    placements = {}
    for pi, page in enumerate(doc):
        for info in page.get_image_info(xrefs=True):
            xref = info["xref"]
            if xref in placements:
                continue
            bbox = info["bbox"]
            bw = bbox[2] - bbox[0]
            dpi = info["width"] / (bw / 72) if bw else 0
            placements[xref] = (pi, dpi)

    for xref, (dpi_target, quality) in RASTER.items():
        pi, dpi_now = placements[xref]
        im = scaled_image(doc, xref, dpi_now, dpi_target)
        stream = to_jpeg(im, quality)
        doc[pi].replace_image(xref, stream=stream)
        if doc.xref_get_key(xref, "SMask")[0] != "null":
            doc.xref_set_key(xref, "SMask", "null")
        print(f"xref {xref}: {dpi_now:.0f} -> {dpi_target} dpi {im.size} {len(stream)/1024:.0f} KB")

    holder = doc.new_page(width=10, height=10)
    img_xref = holder.insert_image(holder.rect, stream=jpeg)
    doc.delete_page(doc.page_count - 1)

    bw, bh = form_bbox.width, form_bbox.height
    form = ("q\n%.5f 0 0 %.5f 0 0 cm\n/Im1 Do\nQ\n" % (bw, bh)).encode()
    doc.update_object(
        form_xref,
        "<< /Type /XObject /Subtype /Form /FormType 1 /BBox [ 0 0 %.5f %.5f ] "
        "/Resources << /XObject << /Im1 %d 0 R >> /ProcSet [ /PDF /ImageC ] >> >>" % (bw, bh, img_xref),
    )
    doc.update_stream(form_xref, form, compress=True)

    doc.save(DST, garbage=4, deflate=True, clean=True)
    size = os.path.getsize(DST)
    print(f"wrote {DST} {size} bytes ({size/1024/1024:.2f} MiB)")


if __name__ == "__main__":
    main()

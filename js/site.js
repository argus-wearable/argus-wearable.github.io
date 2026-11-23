(function () {
  var frame = document.getElementById("video-frame");
  var video = document.getElementById("overview-video");
  var poster = document.getElementById("video-poster");
  if (!frame || !video) return;

  video.addEventListener("loadeddata", function () {
    frame.classList.add("is-ready");
    if (poster) {
      poster.setAttribute("alt", "");
      poster.setAttribute("aria-hidden", "true");
    }
  });
})();

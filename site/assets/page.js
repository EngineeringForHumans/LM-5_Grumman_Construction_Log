(function () {
  var mobile = window.matchMedia("(max-width: 47.99em)");
  var mount = document.getElementById("scan-viewer");
  var viewer = null;

  function bootViewer() {
    if (viewer || !mount || mobile.matches) return;
    if (typeof OpenSeadragon === "undefined") return;
    viewer = OpenSeadragon({
      element: mount,
      prefixUrl: mount.dataset.prefix,
      tileSources: mount.dataset.tilesource,
      showNavigator: false,
      showRotationControl: true,
      gestureSettingsMouse: { clickToZoom: false },
      minZoomImageRatio: 0.8,
      maxZoomPixelRatio: 2,
      animationTime: 0.6
    });
  }

  bootViewer();
  if (mobile.addEventListener) {
    mobile.addEventListener("change", bootViewer);
  }

  var buttons = document.querySelectorAll(".text-toggle button");
  var variants = document.querySelectorAll("[data-variant]");

  function setVariant(name, push) {
    buttons.forEach(function (button) {
      button.setAttribute("aria-pressed", String(button.dataset.text === name));
    });
    variants.forEach(function (block) {
      block.hidden = block.dataset.variant !== name;
    });
    if (!push) return;
    var url = new URL(window.location.href);
    if (name === "diplomatic") {
      url.searchParams.delete("text");
    } else {
      url.searchParams.set("text", name);
    }
    history.replaceState({ text: name }, "", url);
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      setVariant(button.dataset.text, true);
    });
  });

  var requested = new URL(window.location.href).searchParams.get("text");
  setVariant(requested === "clean" ? "clean" : "diplomatic", false);
})();

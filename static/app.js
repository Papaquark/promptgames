(function () {
  "use strict";

  var toastTimer = null;

  function getPrompt(button) {
    var id = button.getAttribute("data-prompt-id");
    var prompt = id ? document.getElementById(id) : null;
    return prompt ? prompt.textContent || "" : "";
  }

  function showToast(message, isError) {
    var toast = document.getElementById("toast");
    if (!toast) {
      return;
    }

    toast.textContent = message;
    toast.classList.toggle("is-error", Boolean(isError));
    toast.setAttribute("role", isError ? "alert" : "status");
    toast.classList.add("is-visible");

    if (toastTimer) {
      window.clearTimeout(toastTimer);
    }
    toastTimer = window.setTimeout(function () {
      toast.classList.remove("is-visible");
    }, 5000);
  }

  function fallbackCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "-1000px";
    area.style.left = "-1000px";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, area.value.length);

    var copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (error) {
      copied = false;
    }
    area.remove();

    if (!copied) {
      throw new Error("Copy command failed");
    }
  }

  function copyText(text) {
    if (
      navigator.clipboard &&
      typeof navigator.clipboard.writeText === "function" &&
      window.isSecureContext
    ) {
      return navigator.clipboard.writeText(text).catch(function () {
        fallbackCopy(text);
      });
    }

    try {
      fallbackCopy(text);
      return Promise.resolve();
    } catch (error) {
      return Promise.reject(error);
    }
  }

  function handleCopy(button) {
    var text = getPrompt(button);
    if (!text) {
      showToast("The prompt could not be found on this page.", true);
      return;
    }

    copyText(text).then(
      function () {
        showToast("Prompt copied. Paste it into your AI and press send.");
      },
      function () {
        showToast("Could not copy automatically. Select the prompt and copy it manually.", true);
      }
    );
  }

  function openPlayTab(url) {
    var opened = window.open(url, "_blank");
    if (opened) {
      try {
        opened.opener = null;
      } catch (error) {
        // The tab still opened; some browsers do not expose opener.
      }
    }
    return opened;
  }

  function handlePlay(button) {
    var text = getPrompt(button);
    var url = button.getAttribute("data-play-url") || "https://gemini.google.com/app";

    if (!text) {
      var opened = openPlayTab(url);
      showToast(
        opened
          ? "Gemini opened, but the prompt could not be found. Copy it from the preview."
          : "The new tab was blocked and the prompt could not be found. Select it from the preview.",
        true
      );
      return;
    }

    // Copy while this page still has focus. window.open() consumes user activation
    // and moves focus to the new tab, which makes clipboard writes fail.
    copyText(text).then(
      function () {
        var opened = openPlayTab(url);
        showToast(
          opened
            ? "Prompt copied. Paste it into Gemini and press send."
            : "Prompt copied, but the new tab was blocked. Open Gemini and paste it there.",
          !opened
        );
      },
      function () {
        var opened = openPlayTab(url);
        showToast(
          opened
            ? "Gemini opened, but the prompt could not be copied. Select it from the preview and copy it manually."
            : "The new tab was blocked and the prompt could not be copied. Select it from the preview and copy it manually.",
          true
        );
      }
    );
  }

  function initExpanders() {
    var buttons = document.querySelectorAll("[data-expand]");
    Array.prototype.forEach.call(buttons, function (button) {
      var frameId = button.getAttribute("data-target");
      var frame = frameId ? document.getElementById(frameId) : null;
      if (!frame) {
        return;
      }

      var prompt = frame.querySelector(".prompt-preview");
      if (!prompt) {
        return;
      }

      var expanded = false;

      function refresh() {
        if (expanded) {
          return;
        }
        var shouldCollapse = prompt.scrollHeight > 520;
        frame.classList.toggle("is-collapsed", shouldCollapse);
        button.hidden = !shouldCollapse;
        button.setAttribute("aria-expanded", "false");
        button.textContent = "Show full prompt";
      }

      button.addEventListener("click", function () {
        expanded = !expanded;
        frame.classList.toggle("is-collapsed", !expanded);
        button.setAttribute("aria-expanded", expanded ? "true" : "false");
        button.textContent = expanded ? "Show less" : "Show full prompt";

        if (!expanded) {
          var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          frame.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
        }
      });

      refresh();

      var resizeTimer = null;
      window.addEventListener("resize", function () {
        if (resizeTimer) {
          window.clearTimeout(resizeTimer);
        }
        resizeTimer = window.setTimeout(refresh, 150);
      });
    });
  }

  document.addEventListener("click", function (event) {
    var target = event.target.closest("[data-copy], [data-play]");
    if (!target) {
      return;
    }

    if (target.hasAttribute("data-play")) {
      handlePlay(target);
    } else {
      handleCopy(target);
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initExpanders);
  } else {
    initExpanders();
  }
})();

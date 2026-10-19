/* Wash Works - progressive enhancement only. Every page works without this
   file; it just makes the mobile nav and the contact form nicer. */
(function () {
  "use strict";

  // --- analytics helper ----------------------------------------------------
  // No-ops safely when GA4 is not configured (gtag never loaded). T-7.
  function track(event, params) {
    if (typeof window.gtag === "function") window.gtag("event", event, params || {});
  }

  // Fire a conversion on every tap of a phone number - the primary CTA.
  document.querySelectorAll('a[href^="tel:"]').forEach(function (link) {
    link.addEventListener("click", function () {
      track("phone_call", { link_url: link.getAttribute("href") });
    });
  });

  // --- hero background video (self-hosted) -------------------------------------
  // static/video/hero.mp4 - see tools/make_hero_video.py. The <video> ships with
  // preload="none" and no autoplay attribute, so nothing downloads until this
  // decides motion is welcome. Visitors who prefer reduced motion, or have Data
  // Saver / a 2G connection, just get the poster frame and a play button they
  // can press themselves. Everyone else gets a pause button too (WCAG 2.2.2:
  // auto-moving content past 5s needs a way to stop it).
  var heroVideo = document.querySelector(".hero__video");
  if (heroVideo) {
    var heroToggle = document.querySelector("[data-video-toggle]");
    var heroSection = heroVideo.closest(".hero");
    var heroConn = navigator.connection || {};
    var heroMotionWelcome = !window.matchMedia("(prefers-reduced-motion: reduce)").matches &&
                            !heroConn.saveData && !/(^|-)2g$/.test(heroConn.effectiveType || "");
    var heroUserPaused = !heroMotionWelcome;   // an opt-out counts as "paused" until they press play
    var heroInView = true;

    var heroShowState = function () {
      if (!heroToggle) return;
      heroToggle.hidden = false;
      heroToggle.setAttribute("aria-pressed", String(heroVideo.paused));
      heroToggle.setAttribute("aria-label",
        heroVideo.paused ? "Play background video" : "Pause background video");
    };
    var heroPlay = function () {
      if (heroUserPaused || !heroInView) return;
      heroVideo.muted = true;   // muted playback is what browsers allow without a click
      var started = heroVideo.play();
      // Autoplay blocked (iOS Low Power Mode, an extension...): leave the poster
      // up and let the visitor start it with the button.
      if (started && started.catch) started.catch(heroShowState);
    };
    var heroGiveUp = function () {
      heroVideo.hidden = true;
      if (heroToggle) heroToggle.hidden = true;
      console.warn("[hero video] could not load - showing the plain hero instead");
    };

    heroVideo.addEventListener("play", heroShowState);
    heroVideo.addEventListener("pause", heroShowState);
    heroVideo.addEventListener("error", heroGiveUp);
    var heroSources = heroVideo.querySelectorAll("source");
    if (heroSources.length) heroSources[heroSources.length - 1].addEventListener("error", heroGiveUp);

    if (heroToggle) {
      heroToggle.addEventListener("click", function () {
        if (heroVideo.paused) { heroUserPaused = false; heroPlay(); }
        else { heroUserPaused = true; heroVideo.pause(); }
      });
    }
    if (!heroMotionWelcome) heroShowState();   // so the play button is there to opt in

    // Play while the tab is visible and the hero is on screen; rest otherwise.
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "visible") heroPlay(); else heroVideo.pause();
    });
    if ("IntersectionObserver" in window && heroSection) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          heroInView = e.isIntersecting;
          if (heroInView) heroPlay(); else heroVideo.pause();
        });
      }, { threshold: 0.05 }).observe(heroSection);
    } else {
      heroPlay();
    }
  }

  // --- mobile nav ----------------------------------------------------------
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("primary-nav");

  function isMobile() {
    return window.matchMedia("(max-width: 60rem)").matches;
  }
  function setNav(open) {
    toggle.setAttribute("aria-expanded", String(open));
    nav.hidden = !open;
  }
  if (toggle && nav) {
    if (isMobile()) setNav(false);
    toggle.addEventListener("click", function () {
      setNav(toggle.getAttribute("aria-expanded") !== "true");
    });
    // Keep the nav visible on desktop regardless of the toggle's last state.
    window.addEventListener("resize", function () {
      if (!isMobile()) nav.hidden = false;
      else if (toggle.getAttribute("aria-expanded") !== "true") nav.hidden = true;
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && isMobile() && toggle.getAttribute("aria-expanded") === "true") {
        setNav(false);
        toggle.focus();
      }
    });
  }

  // --- contact form --------------------------------------------------------
  var form = document.getElementById("contact-form");
  if (!form) return;

  // T-6: stamp the render time so the server can reject instant bot submits.
  var renderedAt = document.getElementById("rendered_at");
  if (renderedAt) renderedAt.value = String(Date.now() / 1000);

  var statusBox = document.getElementById("form-status");

  function clearErrors() {
    form.querySelectorAll("[data-error-for]").forEach(function (el) {
      el.hidden = true;
      el.textContent = "";
      el.closest(".field").removeAttribute("data-invalid");
      var input = form.querySelector("#" + el.getAttribute("data-error-for"));
      if (input) input.removeAttribute("aria-invalid");
    });
  }

  function showFieldErrors(fields, message) {
    (fields || []).forEach(function (name, i) {
      var msg = form.querySelector('[data-error-for="' + name + '"]');
      var input = form.querySelector("#" + name);
      if (msg) {
        msg.textContent = i === 0 ? message : "Required.";
        msg.hidden = false;
        msg.closest(".field").setAttribute("data-invalid", "");
      }
      if (input) input.setAttribute("aria-invalid", "true");
    });
    var first = fields && fields.length ? form.querySelector("#" + fields[0]) : null;
    if (first) first.focus();
  }

  function setStatus(state, message) {
    statusBox.dataset.state = state;
    statusBox.textContent = message;
    statusBox.hidden = false;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearErrors();

    var button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    button.textContent = "Sending...";

    fetch(form.action, { method: "POST", body: new FormData(form), headers: { "X-Requested-With": "fetch" } })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (result) {
        if (result.data.status === "success") {
          form.reset();
          if (renderedAt) renderedAt.value = String(Date.now() / 1000);
          track("generate_lead", { form_id: "contact" });
          setStatus("success", result.data.message);
          statusBox.focus && statusBox.focus();
        } else {
          setStatus("error", result.data.message || "Please check the form and try again.");
          showFieldErrors(result.data.fields, result.data.message);
        }
      })
      .catch(function () {
        setStatus("error", "We couldn't send that. Please call us instead.");
      })
      .finally(function () {
        button.disabled = false;
        button.textContent = "Send message";
      });
  });
})();

/**
 * Custom HA panel host for Advisor UI.
 * Fills the HA content area and injects a live access token into the iframe.
 */
class AutomationAdvisorPanel extends HTMLElement {
  constructor() {
    super();
    this._iframe = null;
    this._lastToken = null;
    this._hass = null;
    this._timer = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._ensureFrame();
    this._syncToken(true);
  }

  get hass() {
    return this._hass;
  }

  set narrow(_narrow) {}
  set panel(_panel) {}

  connectedCallback() {
    // Fill HA panel content (percentage height alone often collapses).
    this.style.cssText = [
      "display:block",
      "position:relative",
      "width:100%",
      "height:100%",
      "min-height:calc(100vh - 56px)",
      "overflow:hidden",
      "background:#07090c",
      "box-sizing:border-box",
    ].join(";");
    this._ensureFrame();
    this._syncToken(true);
    clearInterval(this._timer);
    this._timer = setInterval(() => this._syncToken(false), 20000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    this._timer = null;
  }

  _token() {
    try {
      const hass = this._hass;
      if (!hass || !hass.auth) return null;
      if (hass.auth.data && hass.auth.data.access_token) {
        return hass.auth.data.access_token;
      }
      if (hass.auth.accessToken) return hass.auth.accessToken;
      return null;
    } catch (_) {
      return null;
    }
  }

  _ensureFrame() {
    if (this._iframe) return;
    const iframe = document.createElement("iframe");
    iframe.title = "Dashboard";
    iframe.style.cssText =
      "border:0;position:absolute;inset:0;width:100%;height:100%;display:block;background:#07090c;";
    iframe.allow = "clipboard-write";
    // Placeholder until hass token arrives
    iframe.src =
      "about:blank";
    this._iframe = iframe;
    this.appendChild(iframe);
  }

  _syncToken(force) {
    if (!this._iframe) return;
    const token = this._token();
    if (!token) return;
    if (!force && token === this._lastToken) {
      try {
        this._iframe.contentWindow.postMessage(
          { type: "advisor-ha-token", token },
          location.origin
        );
      } catch (_) {}
      return;
    }
    this._lastToken = token;
    // Hash-only token keeps it out of access logs; /ui is no-cache.
    const url =
      "/api/automation_advisor/ui?v=0.2.28#ha_token=" +
      encodeURIComponent(token);
    this._iframe.src = url;
  }
}

if (!customElements.get("automation-advisor-panel")) {
  customElements.define("automation-advisor-panel", AutomationAdvisorPanel);
}

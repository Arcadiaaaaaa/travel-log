"use strict";

const Platform = (() => {
  const native = window.TravelNative;
  const isNative = Boolean(native);
  let serverOrigin = "";
  let authToken = "";

  const failure = (message, status) => Object.assign(new Error(message), { status });

  async function request(origin, path, method, body, headers = {}, timeout = 15000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const options = { method, headers: { ...headers }, credentials: isNative ? "omit" : "same-origin", signal: controller.signal };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    try {
      const response = await fetch(origin + path, options);
      let data = null;
      try {
        data = await response.json();
      } catch (err) {
        if (err.name !== "SyntaxError") throw err;
      }
      return { response, data };
    } catch {
      const message = controller.signal.aborted ? "连接超时，请检查网络" :
        isNative ? "无法连接到服务器" : "网络连接失败，请检查网络";
      throw failure(message, 0);
    } finally {
      clearTimeout(timer);
    }
  }

  async function checkedRequest(origin, path, method, body, headers) {
    const { response, data } = await request(origin, path, method, body, headers);
    if (!response.ok) throw failure((data && data.error) || `请求失败（${response.status}）`, response.status);
    return data;
  }

  function normalizeServer(value) {
    if (typeof value !== "string" || !value.trim() || value.includes("\\")) throw failure("服务器地址无效", 400);
    let url;
    try {
      const text = value.trim();
      url = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(text) ? text : "https://" + text);
    } catch {
      throw failure("服务器地址无效", 400);
    }
    if (!["https:", "http:"].includes(url.protocol) || !url.hostname || url.username || url.password) {
      throw failure("服务器地址无效", 400);
    }
    if (url.protocol === "http:" && !native.allowInsecureServer) throw failure("只支持 https:// 地址", 400);
    return url.origin;
  }

  async function checkServer(origin) {
    const { response, data } = await request(origin, "/api/meta", "GET", undefined, {}, 10000);
    if (!response.ok || !data || data.app !== "travel-log") throw failure("这不是旅行记录服务器", response.status);
    if (typeof data.api_version === "number" && data.api_version > 1) throw failure("服务器版本较新，请更新 App", response.status);
    if (data.api_version !== 1) throw failure("服务器版本过旧，请先更新服务器", response.status);
  }

  async function clearToken() {
    authToken = "";
    await native.prefs.remove("authToken");
  }

  async function saveWebFile(filename, text, mimeType) {
    const blob = new Blob([text], { type: mimeType });
    const file = new File([blob], filename, { type: mimeType });
    // 手机上用系统分享面板（可存到“文件”App），电脑上直接下载。
    if (matchMedia("(pointer: coarse)").matches && navigator.canShare && navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: filename });
        return;
      } catch (err) {
        if (err.name === "AbortError") return;
      }
    }
    const url = URL.createObjectURL(blob);
    const a = h("a", { href: url, download: filename });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return {
    isNative,
    name: isNative ? native.platform : "web",
    async init() {
      if (!isNative) return;
      // 原生版本只在平台层读取，不给界面增加桥接接口。
      const version = document.getElementById("native-version");
      if (version) version.textContent = `版本：${native.appVersion}`;
      const [origin, token] = await Promise.all([native.prefs.get("serverOrigin"), native.prefs.get("authToken")]);
      serverOrigin = origin ? normalizeServer(origin) : "";
      authToken = token || "";
    },
    apiBase: () => isNative ? serverOrigin : "",
    authHeaders: () => isNative && serverOrigin && authToken ? { Authorization: `Bearer ${authToken}` } : {},
    hasCredentials: () => !isNative || Boolean(serverOrigin && authToken),
    serverLabel: () => serverOrigin ? new URL(serverOrigin).hostname : "",
    async signIn(server, password) {
      if (!isNative) return checkedRequest("", "/api/login", "POST", { password });
      const origin = normalizeServer(server);
      await checkServer(origin);
      const device = native.platform === "ios" ? "iOS" : "Android";
      const data = await checkedRequest(origin, "/api/tokens", "POST", { password, device_name: `${device} App ${native.appVersion}` });
      if (!data || typeof data.token !== "string" || !data.token || data.token_type !== "Bearer") {
        throw failure("这不是旅行记录服务器", 201);
      }
      // 先清旧令牌，防止存储中途失败后把旧凭据配到新服务器。
      await native.prefs.remove("authToken");
      authToken = "";
      await native.prefs.set("serverOrigin", origin);
      serverOrigin = origin;
      await native.prefs.set("authToken", data.token);
      authToken = data.token;
    },
    async signOut() {
      if (!isNative) return checkedRequest("", "/api/logout", "POST");
      try {
        if (serverOrigin && authToken) await checkedRequest(serverOrigin, "/api/tokens/current", "DELETE", undefined, this.authHeaders());
      } catch {
        // 服务器不可用时仍退出本机登录状态。
      } finally {
        await clearToken();
      }
    },
    async forgetServer() {
      if (!isNative) return this.signOut();
      try {
        await this.signOut();
      } finally {
        serverOrigin = "";
        await native.prefs.remove("serverOrigin");
      }
    },
    async onUnauthorized() {
      if (isNative) await clearToken();
    },
    async saveFile(filename, text, mimeType) {
      if (isNative) return native.shareFile(filename, text, mimeType);
      return saveWebFile(filename, text, mimeType);
    },
    onBackButton(handler) {
      if (isNative) native.onBackButton(handler);
    },
  };
})();

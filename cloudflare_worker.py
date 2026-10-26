"""Cloudflare Worker 入口；业务API由 cloudflare_core 处理。"""
from urllib.parse import unquote, urlparse

import js
from workers import Response, WorkerEntrypoint

import server
from cloudflare_core import CloudflareApp


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = unquote(urlparse(request.url).path)
        method = str(request.js_object.method)
        head = method == "HEAD"
        if path.startswith("/api/"):
            app = CloudflareApp(self.env.DB, getattr(self.env, "PASSWORD_HASH", ""),
                                getattr(self.env, "TRAVEL_CORS_ORIGINS", "https://localhost,capacitor://localhost"))
            headers = dict(request.headers.items())
            body = bytearray()
            if request.body:
                reader = request.body.getReader()
                try:
                    while True:
                        chunk = await reader.read()
                        if chunk.done:
                            break
                        body.extend(bytes(chunk.value.to_py()))
                        if len(body) > server.MAX_BODY:
                            await reader.cancel()
                            break
                finally:
                    reader.releaseLock()
            result = await app.handle("GET" if head else method, path, headers, bytes(body),
                                      request.headers.get("CF-Connecting-IP", "local"))
            return Response(None if head or result.status == 204 else result.body,
                            status=result.status, headers=result.headers)
        if method not in ("GET", "HEAD"):
            return Response('{"error":"不支持的请求方法"}',status=405,
                            headers={**server.SECURITY_HEADERS,"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"})
        target = request.js_object
        if path == "/favicon.ico":
            url = js.URL.new(request.url)
            url.pathname = "/icons/icon-192.png"
            target = js.Request.new(url.toString(),request.js_object)
        asset = await self.env.ASSETS.fetch(target)
        # 复制响应以便给静态资源附上与本地服务相同的安全头。
        response = asset if isinstance(asset, Response) else Response(asset)
        safe_headers = dict(response.headers.items())
        safe_headers.update(server.SECURITY_HEADERS)
        safe_headers["Cache-Control"] = "no-cache"
        return Response(response.body,status=response.status,headers=safe_headers)

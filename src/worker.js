export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return new Response("ok\n", {
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }

    if (url.pathname !== "/answer") {
      return new Response("Not found\n", { status: 404 });
    }

    if (request.method !== "POST") {
      return new Response("POST required\n", { status: 405 });
    }

    if (!env.ANSWER_TOKEN) {
      return new Response("ANSWER_TOKEN secret is not configured\n", {
        status: 500,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }

    if (url.searchParams.get("token") !== env.ANSWER_TOKEN) {
      return new Response("Unauthorized\n", {
        status: 401,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }

    // Proxmox VE automated install sends machine details as POST JSON.
    // Static-answer mode does not need those details, so consume and ignore them.
    await request.json().catch(() => ({}));

    if (!env.ANSWER_TOML) {
      return new Response("ANSWER_TOML secret is not configured\n", {
        status: 500,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }

    return new Response(env.ANSWER_TOML, {
      status: 200,
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  },
};

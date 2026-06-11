const DEFAULT_GITHUB_RAW_BASE_URL =
  "https://raw.githubusercontent.com/buddy9880/pve-unattended-install/refactor-cloudflare-answer-server";
const NODE_MAP_PATH = "vars/pve-node.yml";

const TEXT_HEADERS = { "content-type": "text/plain; charset=utf-8" };
const ANSWER_HEADERS = {
  ...TEXT_HEADERS,
  "cache-control": "no-store",
};

function textResponse(body, status = 200) {
  return new Response(body, {
    status,
    headers: TEXT_HEADERS,
  });
}

function normalizeMac(mac) {
  return typeof mac === "string" ? mac.toLowerCase() : "";
}

function normalizeBaseUrl(baseUrl) {
  return String(baseUrl || DEFAULT_GITHUB_RAW_BASE_URL).replace(/\/+$/, "");
}

function githubRawUrl(env, path) {
  return `${normalizeBaseUrl(env.GITHUB_RAW_BASE_URL)}/${path.replace(/^\/+/, "")}`;
}

async function fetchText(url, label) {
  const response = await fetch(url, {
    headers: {
      accept: "text/plain",
      "user-agent": "pve-answer-worker",
    },
  });

  if (!response.ok) {
    throw new Error(`${label} fetch failed with HTTP ${response.status}`);
  }

  return response.text();
}

function parseNodeMap(text) {
  const nodes = new Map();
  let currentNode = null;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(/#.*$/, "").trim();
    if (!line || line === "nodes:") {
      continue;
    }

    const nodeMatch = line.match(/^([A-Za-z0-9_-]+):$/);
    if (nodeMatch) {
      currentNode = {
        name: nodeMatch[1],
        mac: "",
      };
      continue;
    }

    const macMatch = line.match(/^mac_address:\s*["']?([^"']+)["']?$/);
    if (macMatch && currentNode) {
      currentNode.mac = normalizeMac(macMatch[1].trim());
      if (currentNode.mac) {
        nodes.set(currentNode.mac, currentNode.name);
      }
    }
  }

  return nodes;
}

function getNetworkMacs(systemInfo) {
  if (!Array.isArray(systemInfo?.network_interfaces)) {
    return [];
  }

  return systemInfo.network_interfaces
    .map((iface) => normalizeMac(iface?.mac))
    .filter(Boolean);
}

function selectNode(systemInfo, nodesByMac) {
  const macs = new Set(getNetworkMacs(systemInfo));

  for (const mac of macs) {
    const nodeName = nodesByMac.get(mac);
    if (!nodeName) {
      continue;
    }

    return {
      name: nodeName,
      matchedBy: `mac ${mac}`,
    };
  }

  return null;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return textResponse("ok\n");
    }

    if (url.pathname === "/nodes") {
      try {
        const nodeMap = await fetchText(githubRawUrl(env, NODE_MAP_PATH), NODE_MAP_PATH);
        return new Response(nodeMap, {
          status: 200,
          headers: ANSWER_HEADERS,
        });
      } catch (error) {
        console.error(error);
        return textResponse("Node map is not available\n", 502);
      }
    }

    if (url.pathname !== "/answer") {
      return new Response("Not found\n", { status: 404 });
    }

    if (request.method !== "POST") {
      return new Response("POST required\n", { status: 405 });
    }

    // Proxmox VE automated install sends machine details as POST JSON.
    const systemInfo = await request.json().catch(() => null);
    if (!systemInfo) {
      return textResponse("Invalid or missing system-info JSON\n", 400);
    }

    let nodesByMac;
    try {
      nodesByMac = parseNodeMap(await fetchText(githubRawUrl(env, NODE_MAP_PATH), NODE_MAP_PATH));
    } catch (error) {
      console.error(error);
      return textResponse("Node map is not available\n", 502);
    }

    const selectedNode = selectNode(systemInfo, nodesByMac);
    if (!selectedNode) {
      return textResponse("No answer file configured for this machine\n", 404);
    }

    const answerPath = `vars/${selectedNode.name}.toml`;
    let answerBody;
    try {
      answerBody = await fetchText(githubRawUrl(env, answerPath), answerPath);
    } catch (error) {
      console.error(error);
      return textResponse("Answer file is not available\n", 502);
    }

    console.log(
      `Serving ${selectedNode.name} answer file matched by ${selectedNode.matchedBy}`,
    );

    return new Response(answerBody, {
      status: 200,
      headers: ANSWER_HEADERS,
    });
  },
};

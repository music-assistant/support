// OpenAI-shaped embeddings endpoint, served from the CI runner.
//
// The triage bot speaks verbatim OpenAI API and takes its endpoint from
// TRIAGE_EMBED_ENDPOINT, so pointing it at this process needs no Python
// changes at all. This exists because GitHub Models was retired and no
// GitHub-hosted embeddings endpoint replaced it.
//
// CI-only. Nothing under .github/scripts imports this, and the bot has no
// Node dependency at runtime.
//
// Two details are load-bearing:
//
//   Pooling is LAST-token, not mean. Qwen3-Embedding is a causal model and
//   mean pooling silently produces worse vectors — measurably worse retrieval
//   from a server that looks like it is working.
//
//   Inputs are embedded one at a time regardless of how many the caller sends.
//   Attention cost grows with batch x tokens^2: a batch of 8 at the 2048-token
//   cap peaks around 24 GB, where one at a time stays near 4.5 GB and fits a
//   runner. Throughput is unchanged either way since the model is already
//   using every core.
//
//   node server.mjs [port]

import { createServer } from "node:http";
import { AutoModel, AutoTokenizer, env } from "@huggingface/transformers";

// Pinned to a revision SHA, not a tag: a tag is mutable, and a model that
// changes underneath us would silently alter every vector while the index
// header still reported the same model string.
const MODEL = "onnx-community/Qwen3-Embedding-0.6B-ONNX";
const MODEL_REVISION = "c25a394dd583836952667c12f008335071b3f43d";
const MODEL_DTYPE = "q8";
const MAX_TOKENS = 2048; // covers the bot's MAX_POST_EMBED_CHARS of 6000

const port = Number(process.argv[2] ?? process.env.PORT ?? 11435);

// Weights live outside node_modules so CI can cache them on their own key:
// they change only when the model does, while the dependency tree changes
// whenever the lockfile does.
if (process.env.MODEL_CACHE_DIR) env.cacheDir = process.env.MODEL_CACHE_DIR;

const tokenizer = await AutoTokenizer.from_pretrained(MODEL, {
	revision: MODEL_REVISION,
});
const model = await AutoModel.from_pretrained(MODEL, {
	revision: MODEL_REVISION,
	dtype: MODEL_DTYPE,
});

/** The final non-padding position, L2-normalised. */
function poolLast(hidden, mask, dims) {
	const [, seq, width] = dims;
	let last = 0;
	for (let s = 0; s < seq; s++) if (Number(mask[s]) === 1) last = s;
	const row = Array.from(hidden.slice(last * width, last * width + width), Number);
	const norm = Math.hypot(...row) || 1;
	return row.map((x) => x / norm);
}

async function embedOne(text) {
	const encoded = await tokenizer([text], {
		padding: true,
		truncation: true,
		max_length: MAX_TOKENS,
	});
	const output = await model(encoded);
	const hidden = output.last_hidden_state;
	return poolLast(hidden.data, encoded.attention_mask.data, hidden.dims);
}

function send(res, status, body) {
	const payload = JSON.stringify(body);
	res.writeHead(status, {
		"Content-Type": "application/json",
		"Content-Length": Buffer.byteLength(payload),
	});
	res.end(payload);
}

const server = createServer((req, res) => {
	if (req.method === "GET" && req.url === "/health") {
		return send(res, 200, {
			status: "ok",
			model: MODEL,
			revision: MODEL_REVISION,
			dtype: MODEL_DTYPE,
			// The identifier the bot records in the index header. It carries the
			// revision and dtype because the index's `model` field is a
			// compatibility key: anything that would change the vectors has to
			// change this string, or a stale index is silently accepted.
			embedModel: `${MODEL}@${MODEL_REVISION.slice(0, 12)}@${MODEL_DTYPE}`,
		});
	}
	if (req.method !== "POST" || !req.url.endsWith("/embeddings")) {
		return send(res, 404, { error: { message: "not found" } });
	}
	let raw = "";
	req.on("data", (chunk) => {
		raw += chunk;
	});
	req.on("end", async () => {
		try {
			const body = JSON.parse(raw || "{}");
			const inputs = Array.isArray(body.input) ? body.input : [body.input];
			const data = [];
			for (const [index, text] of inputs.entries()) {
				data.push({
					object: "embedding",
					index,
					embedding: await embedOne(String(text ?? "")),
				});
			}
			// `dimensions` is deliberately not honoured: this serves the model's
			// native width. The bot records the width it observes rather than the
			// one it asked for, so an unhonoured request cannot produce a header
			// that misdescribes the file.
			send(res, 200, { object: "list", model: MODEL, data });
		} catch (err) {
			send(res, 500, { error: { message: String(err?.message ?? err) } });
		}
	});
});

server.listen(port, "127.0.0.1", () => {
	console.log(`embeddings server listening on http://127.0.0.1:${port}`);
});

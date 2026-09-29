import os
from flask import Flask, request, jsonify, send_from_directory

# The whole RAG pipeline we built: search + AI providers. Importing it loads the
# database and models once, when the server starts.
from companion import answer

STATIC_DIR = "static"

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


@app.route("/")
def home():
    # Serve the chat page (static/index.html) when you open the site.
    if not os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        return "Backend is running. The chat page (static/index.html) isn't built yet."
    return send_from_directory(STATIC_DIR, "index.html")


@app.post("/api/chat")
def chat():
    # The browser sends JSON like {"question": "who is Sully?"}
    data = request.get_json(silent=True) or {}
    question = str(data.get("question", "")).strip()

    if question == "":
        return jsonify({"error": "Please type a question first."}), 400

    try:
        reply, sources, answered_by = answer(question)
    except Exception as error:
        return jsonify({"error": f"The companion couldn't answer right now. {error}"}), 503

    # We send back JSON like {"answer": "...", "sources": [...], "answered_by": "Groq · ..."}
    return jsonify({"answer": reply, "sources": sources, "answered_by": answered_by})


if __name__ == "__main__":
    print("\nOpen http://127.0.0.1:5000 in your browser. Press Ctrl+C to stop.\n")
    app.run(host="127.0.0.1", port=5000, debug=False)

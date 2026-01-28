from flask import Flask, request, jsonify, render_template_string
from job_rag import JobRAG

app = Flask(__name__)
DB_URL = "postgresql+psycopg2://postgres:dbda123@localhost:35432/postgres"
rag = JobRAG(DB_URL)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Job Search RAG</title>
    <style>
        body { font-family: Arial; margin: 40px; }
        input { width: 400px; padding: 10px; margin: 10px 0; }
        button { padding: 10px 20px; background: #007cba; color: white; border: none; cursor: pointer; }
        .job { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .response { background: #f5f5f5; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .match-score { color: #007cba; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Job Search Assistant</h1>
    <input type="text" id="query" placeholder="Ask about jobs..." />
    <button onclick="search()">Search</button>
    <div id="results"></div>
    
    <script>
    function search() {
        const query = document.getElementById('query').value;
        if (!query) return;
        
        document.getElementById('results').innerHTML = 'Searching...';
        
        fetch('/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({query: query})
        })
        .then(r => r.json())
        .then(data => {
            let html = '<div class="response"><h3>Response:</h3><p>' + data.response + '</p></div>';
            html += '<h3>Jobs Found:</h3>';
            data.jobs.forEach(job => {
                const matchScore = Math.round(job.similarity * 100);
                html += `<div class="job">
                    <h4>${job.title} <span style="color: #007cba; font-size: 14px;">(${matchScore}% match)</span></h4>
                    <p><strong>Role:</strong> ${job.role} | <strong>Location:</strong> ${job.location} | <strong>Experience:</strong> ${job.experience}</p>
                    <p>${job.description.substring(0, 200)}...</p>
                    <a href="${job.apply_url}" target="_blank">Apply</a>
                </div>`;
            });
            document.getElementById('results').innerHTML = html;
        })
        .catch(e => {
            document.getElementById('results').innerHTML = 'Error: ' + e.message;
        });
    }
    
    document.getElementById('query').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') search();
    });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML)

@app.route('/search', methods=['POST'])
def search():
    try:
        query = request.json['query']
        result = rag.chat(query)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "response": "Search failed", "jobs": []}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
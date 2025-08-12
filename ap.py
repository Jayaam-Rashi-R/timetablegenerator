# app.py
from flask import Flask, request, jsonify, send_file
import io
import datetime
import random
import os

app = Flask(__name__)

# -----------------------
# Helper: generate HTML table
# -----------------------
def generate_timetable_html(days_list, subjects, periods_per_subject, hours_per_day, title=None):
    """
    days_list: ['Monday','Tuesday',...']
    subjects: ['Math','Eng',...]
    periods_per_subject: {'Math':2, 'Eng':3, ...}
    hours_per_day: int
    """
    # Build a subject pool list (subject repeated by its count)
    pool = []
    for s in subjects:
        count = periods_per_subject.get(s, 1)
        if count > 0:
            pool += [s] * int(count)

    timetable = {}
    # For each day, shuffle a copy of the pool and pick hours_per_day items
    for day in days_list:
        p = pool.copy()
        random.shuffle(p)
        day_schedule = []
        for i in range(hours_per_day):
            if p:
                day_schedule.append(p.pop(0))
            else:
                # No more allocated periods => Free Period
                day_schedule.append("Free")
        timetable[day] = day_schedule

    # Build HTML
    title_text = title or f"Generated Timetable - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    html = f"<html><head><meta charset='utf-8'><title>{title_text}</title>"
    html += "<style>body{font-family:Arial;margin:20px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #333;padding:8px;text-align:center}th{background:#eee}</style>"
    html += "</head><body>"
    html += f"<h2>{title_text}</h2>"
    html += "<table>"
    # header row
    html += "<tr><th>Day</th>" + "".join(f"<th>Period {i+1}</th>" for i in range(hours_per_day)) + "</tr>"
    # rows
    for day in days_list:
        row = timetable[day]
        html += "<tr>"
        html += f"<td><strong>{day}</strong></td>"
        html += "".join(f"<td>{cell}</td>" for cell in row)
        html += "</tr>"
    html += "</table>"
    html += "</body></html>"
    return html

# -----------------------
# Route: Page 1 - Input form (raw HTML returned)
# -----------------------
@app.route("/", methods=["GET"])
def index_page():
    return """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Timetable Generator — Input</title>
  <style>
    body { font-family: Arial; margin: 30px; max-width: 820px; }
    label { display: block; margin-top: 12px; font-weight:600; }
    input[type=text], textarea, input[type=number] { width: 100%; padding: 8px; margin-top:6px; box-sizing:border-box; }
    button { margin-top: 14px; padding: 10px 14px; cursor: pointer; }
    small { color:#555; }
    .row { display:flex; gap:10px; }
    .half { flex:1; }
  </style>
</head>
<body>
  <h1>Timetable Generator</h1>
  <p>Enter the details below. Then press <strong>Generate</strong> to go to the timetable page.</p>

  <label>Days (comma separated)</label>
  <input id="days" type="text" placeholder="Monday,Tuesday,Wednesday,Thursday,Friday" value="Monday,Tuesday,Wednesday,Thursday,Friday">

  <label>Subjects (comma separated)</label>
  <input id="subjects" type="text" placeholder="Math,English,Science,Computer" value="Math,English,Science,Computer">

  <label>Periods per subject (format: Subject:count, comma separated)</label>
  <input id="periods" type="text" placeholder="Math:8,English:6,Science:8,Computer:4" value="Math:8,English:6,Science:8,Computer:4">
  <small>Counts are total periods across the whole timetable (not per day). Example: Math:8</small>

  <label>Total hours per day</label>
  <input id="hours" type="number" value="6" min="1">

  <div style="margin-top:18px">
    <button onclick="goGenerate()">Generate Timetable →</button>
  </div>

  <script>
    function parseSubjects(input) {
      return input.split(',').map(s => s.trim()).filter(Boolean);
    }
    function parsePeriodsMap(input) {
      const map = {};
      if (!input.trim()) return map;
      input.split(',').forEach(pair => {
        const parts = pair.split(':');
        if (parts.length === 2) {
          const key = parts[0].trim();
          const val = parseInt(parts[1].trim());
          if (key && !isNaN(val) && val >= 0) map[key] = val;
        }
      });
      return map;
    }
    function goGenerate() {
      const days = document.getElementById('days').value.split(',').map(s => s.trim()).filter(Boolean);
      const subjects = parseSubjects(document.getElementById('subjects').value);
      const periods_map = parsePeriodsMap(document.getElementById('periods').value);
      const hours = parseInt(document.getElementById('hours').value) || 6;

      if (days.length === 0 || subjects.length === 0) {
        alert('Please provide at least one day and one subject.');
        return;
      }

      // Ensure periods_map has entries for all subjects (default 1)
      const final_map = {};
      subjects.forEach(s => { final_map[s] = periods_map[s] !== undefined ? periods_map[s] : 1; });

      const payload = { days: days, subjects: subjects, periods_per_subject: final_map, total_hours: hours };
      // Save to localStorage for the timetable page to read
      localStorage.setItem('timetablePayload', JSON.stringify(payload));
      // Navigate to timetable page
      window.location.href = '/timetable';
    }
  </script>
</body>
</html>
"""

# -----------------------
# Route: Page 2 - Display generated timetable (raw HTML)
# -----------------------
@app.route("/timetable", methods=["GET"])
def timetable_page():
    # This page will read payload from localStorage, call /generate-timetable to get HTML, then show it.
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Timetable Generator — Result</title>
<style>
  body { font-family: Arial; margin: 20px; max-width: 1000px; }
  #container { margin-top: 10px; }
  button { padding: 8px 12px; margin-right: 8px; cursor:pointer; }
  #message { color: #777; margin-top: 6px; }
</style>
</head>
<body>
  <h1>Generated Timetable</h1>
  <div>
    <button id="regenerateBtn">Regenerate</button>
    <button id="downloadBtn">Download as .html</button>
    <button id="backBtn">Back to Input</button>
    <span id="message"></span>
  </div>

  <div id="container" style="margin-top:16px">Loading timetable...</div>

<script>
  async function fetchAndShow() {
    const raw = localStorage.getItem('timetablePayload');
    if (!raw) {
      document.getElementById('container').innerHTML = '<p style="color:red">No input found. Please go back and enter details.</p>';
      return;
    }
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch(e) {
      document.getElementById('container').innerHTML = '<p style="color:red">Invalid input data. Please re-enter.</p>';
      return;
    }
    document.getElementById('message').innerText = 'Generating...';
    try {
      const res = await fetch('/generate-timetable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const err = await res.json();
        document.getElementById('container').innerHTML = `<p style="color:red">Error: ${err.message || res.status}</p>`;
        document.getElementById('message').innerText = '';
        return;
      }
      const data = await res.json();
      // data.html contains the full HTML of the timetable table (a full html page)
      // We will embed only the table portion by extracting <table>...</table>
      const html = data.html || '';
      // Insert HTML directly (safe enough here because server created it from user input)
      document.getElementById('container').innerHTML = html;
      // Also store last generated html in localStorage for download
      localStorage.setItem('lastGeneratedHtml', html);
      document.getElementById('message').innerText = 'Done';
    } catch (e) {
      document.getElementById('container').innerHTML = `<p style="color:red">Error generating timetable: ${e.message}</p>`;
      document.getElementById('message').innerText = '';
    }
  }

  document.getElementById('regenerateBtn').addEventListener('click', fetchAndShow);
  document.getElementById('backBtn').addEventListener('click', () => window.location.href = '/');
  document.getElementById('downloadBtn').addEventListener('click', async () => {
    const html = localStorage.getItem('lastGeneratedHtml') || '';
    if (!html) {
      alert('No generated timetable to download. Click Regenerate first.');
      return;
    }
    // Ask backend to create download response
    const filename = 'timetable_' + new Date().toISOString().slice(0,19).replace(/[:T]/g,'-') + '.html';
    const res = await fetch('/download-timetable', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html: html, filename: filename })
    });
    if (!res.ok) {
      const err = await res.json();
      alert('Download failed: ' + (err.message || res.status));
      return;
    }
    // Get blob and force download
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  // auto-run on load
  fetchAndShow();
</script>
</body>
</html>
"""

# -----------------------
# API: Generate timetable (returns HTML)
# -----------------------
@app.route("/generate-timetable", methods=["POST"])
def api_generate_timetable():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Invalid request, JSON required"}), 400

    days = data.get("days")
    subjects = data.get("subjects")
    periods_map = data.get("periods_per_subject", {})
    total_hours = int(data.get("total_hours", data.get("total_hours", 6)))

    # basic validation
    if not isinstance(days, list) or not days:
        return jsonify({"message": "days must be a non-empty list"}), 400
    if not isinstance(subjects, list) or not subjects:
        return jsonify({"message": "subjects must be a non-empty list"}), 400
    try:
        hours = int(total_hours)
        if hours <= 0: raise ValueError()
    except Exception:
        return jsonify({"message": "total_hours must be a positive integer"}), 400

    # Ensure periods_map contains integer counts for all subjects
    final_map = {}
    for s in subjects:
        val = periods_map.get(s, 1)
        try:
            n = int(val)
            if n < 0:
                n = 0
        except Exception:
            n = 1
        final_map[s] = n

    html = generate_timetable_html(days, subjects, final_map, hours)
    return jsonify({"html": html}), 200

# -----------------------
# API: Download timetable (POST with JSON {html, filename})
# -----------------------
@app.route("/download-timetable", methods=["POST"])
def api_download_timetable():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Invalid request"}), 400
    html = data.get("html", "")
    filename = data.get("filename", f"timetable_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.html")
    if not html:
        return jsonify({"message": "No HTML provided"}), 400

    # Return HTML as file attachment using BytesIO
    bio = io.BytesIO()
    bio.write(html.encode("utf-8"))
    bio.seek(0)
    # safe filename: strip path separators
    filename = os.path.basename(filename)
    return send_file(bio, mimetype="text/html", as_attachment=True, download_name=filename)

# -----------------------
if __name__ == "__main__":
    # Use port 8080 to match earlier examples
    app.run(debug=True, port=8080)


"""Custom admin widget that renders a JSONField of key-value pairs
as a user-friendly dynamic table with Add/Remove row buttons.
No model or migration changes are needed — the widget serialises
back to JSON before Django processes the form.
"""

import json
from django import forms
from django.utils.safestring import mark_safe


class KeyValueWidget(forms.Widget):
    """Renders a JSON dict as an editable table of (key, value) rows."""

    template_name = None  # We render via Python, not a template file and why is that why can't we have use the  html

    class Media:  # what does evene do
        css = {"all": []}  # i need to make the ui look black
        js = []

    def _parse_value(self, value):  # what is this class an why does it syaty wtht the _
        """Return a list of (key, val) tuples from a JSON string or dict."""
        if not value:
            return []
        if isinstance(value, dict):
            return list(value.items())
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return list(parsed.items())
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    def value_from_datadict(self, data, files, name):
        """Collect dynamic rows submitted by the form and return JSON string."""
        keys = data.getlist(f"{name}_key")
        values = data.getlist(f"{name}_value")
        result = {}
        for k, v in zip(keys, values):
            k = k.strip()  # what does this even do
            if k:  # skip blank keys
                result[k] = v.strip()  # so we are converting the dict into a json
        return json.dumps(result, ensure_ascii=False)

    def render(
        self, name, value, attrs=None, renderer=None
    ):  # is this function like the overloading function of the defualt render
        pairs = self._parse_value(value)

        # ── Styles (injected once; duplicates are harmless) ───────
        # what are these style comes from i meanss wwhat are tjose .kv means and how does they evenwork where do they processed by
        styles = """ 
        <style>
        .kv-table-wrapper{font-family:inherit;margin-top:4px}
        .kv-table{width:100%;border-collapse:collapse;margin-bottom:8px}
        .kv-table th{text-align:left;padding:6px 10px;font-size:11px;
          font-weight:700;text-transform:uppercase;letter-spacing:.06em;
          background:#f8f8f8;border:1px solid #e0e0e0;color:#555}
        .kv-table td{padding:4px 6px;border:1px solid #e0e0e0;vertical-align:middle}
        .kv-table input[type=text]{width:100%;border:1px solid #ccc;border-radius:4px;
          padding:5px 8px;font-size:13px;box-sizing:border-box;outline:none}
        .kv-table input[type=text]:focus{border-color:#447e9b;box-shadow:0 0 0 2px #447e9b33}
        .kv-btn{display:inline-flex;align-items:center;gap:4px;padding:5px 12px;
          border:none;border-radius:4px;font-size:12px;font-weight:700;
          cursor:pointer;transition:opacity .15s}
        .kv-btn-add{background:#447e9b;color:#fff}
        .kv-btn-add:hover{opacity:.85}
        .kv-btn-remove{background:#e74c3c;color:#fff;padding:4px 8px;font-size:11px}
        .kv-btn-remove:hover{opacity:.8}
        </style>
        """

        # ── Existing rows ─────────────────────────────────────────
        rows_html = ""
        for k, v in pairs:  # what does this fe loop do
            k_esc = str(k).replace('"', "&quot;")
            v_esc = str(v).replace('"', "&quot;")
        # the below formating is bad isn't it
        rows_html += f"""
             <tr>
               <td><input type="text" name="{name}_key"   value="{k_esc}" placeholder="e.g. RAM" /></td>
               <td><input type="text" name="{name}_value" value="{v_esc}" placeholder="e.g. 8 GB" /></td>
               <td style="width:60px;text-align:center">
                 <button type="button" class="kv-btn kv-btn-remove">✕</button>
               </td>
             </tr>"""

        # ── Template row stored as a hidden HTML template element ─
        # Using a <template> tag means the browser never renders it,
        # so there are no ID conflicts and no need to find by ID.i don;t understand what the below thing so
        row_template = f""" 
            <template id="{name}_row_tpl">
              <tr>
                <td><input type="text" name="{name}_key"   placeholder="e.g. RAM" /></td>
                <td><input type="text" name="{name}_value" placeholder="e.g. 8 GB" /></td>
                <td style="width:60px;text-align:center">
                  <button type="button" class="kv-btn kv-btn-remove">✕</button>
                </td>
              </tr>
            </template>"""

        # ── Full widget HTML ──────────────────────────────────────
        table_html = f"""
            {styles}
            {row_template}
            <div class="kv-table-wrapper" data-kv-field="{name}">
              <table class="kv-table">
                <thead>
                  <tr>
                    <th>Specification Name</th>
                    <th>Value</th>
                    <th style="width:60px"></th>
                  </tr>
                </thead>
                <tbody class="kv-tbody">
                  {rows_html}
                </tbody>
              </table>
              <button type="button" class="kv-btn kv-btn-add" data-tpl="{name}_row_tpl">
                &#xff0b; Add Specification
              </button>
            </div>

            <script>
            (function () {{
              // Use event delegation on document so it works regardless of tab visibility
              // or any DOM manipulation done by Jazzmin/AdminLTE.
              if (window.__kvDelegationAttached) return;   // attach only once
              window.__kvDelegationAttached = true;
            
              document.addEventListener('click', function (e) {{
                // ── Add row ────────────────────────────────────────────────
                var addBtn = e.target.closest('.kv-btn-add');
                if (addBtn) {{
                  var tplId = addBtn.getAttribute('data-tpl');
                  var tpl   = document.getElementById(tplId);
                  var wrapper = addBtn.closest('.kv-table-wrapper');
                  var tbody   = wrapper ? wrapper.querySelector('.kv-tbody') : null;
                  if (tpl && tbody) {{
                    var clone = tpl.content.cloneNode(true);
                    tbody.appendChild(clone);
                    var last = tbody.lastElementChild;
                    if (last) last.querySelector('input').focus();
                  }}
                  return;
                }}

    // ── Remove row ─────────────────────────────────────────────
                var removeBtn = e.target.closest('.kv-btn-remove');
                if (removeBtn) {{
                  var row = removeBtn.closest('tr');
                  if (row) row.remove();
                }}
              }});
            }})();
            </script>
            """
        return mark_safe(table_html)

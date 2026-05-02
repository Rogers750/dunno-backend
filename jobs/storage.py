import logging

from database.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

_BUCKET = "resumes"



def render_resume_html(resume_json: dict) -> str:
    """Convert resume JSON to a clean, print-ready HTML page."""
    b = resume_json.get("basics", {})
    experiences = resume_json.get("experience", [])
    educations = resume_json.get("education", [])
    skills = resume_json.get("skills", {})
    projects = resume_json.get("projects", [])

    def _tag(tag, content, **attrs):
        attr_str = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
        return f"<{tag}{attr_str}>{content}</{tag}>"

    def _bullets(items):
        if not items:
            return ""
        lis = "".join(_tag("li", i) for i in items)
        return _tag("ul", lis)

    exp_html = ""
    for e in sorted(experiences, key=lambda x: x.get("sortDate", ""), reverse=True):
        end = "Present" if e.get("endSortDate", "") >= "9999" else e.get("endDate", "")
        header = f"<div class='row'><strong>{e.get('role','')}</strong><span>{e.get('startDate','')} – {end}</span></div>"
        sub = f"<div class='row'><em>{e.get('company','')}{', ' + e['location'] if e.get('location') else ''}</em></div>"
        exp_html += f"<div class='entry'>{header}{sub}{_bullets(e.get('bullets',[]))}</div>"

    edu_html = ""
    for e in sorted(educations, key=lambda x: x.get("sortDate", ""), reverse=True):
        header = f"<div class='row'><strong>{e.get('institution','')}</strong><span>{e.get('startDate','')} – {e.get('endDate','')}</span></div>"
        sub = f"<div class='row'><em>{e.get('degree','')}</em>{(' · GPA ' + e['gpa']) if e.get('gpa') else ''}</div>"
        edu_html += f"<div class='entry'>{header}{sub}</div>"

    skill_parts = []
    for category, items in skills.items() if isinstance(skills, dict) else []:
        if items:
            skill_parts.append(f"<strong>{category.capitalize()}:</strong> {', '.join(items)}")
    skills_html = "<br>".join(skill_parts)

    proj_html = ""
    for p in projects[:4]:
        tech = ", ".join(p.get("techStack", []))
        header = f"<div class='row'><strong>{p.get('name','')}</strong>{('<span>' + tech + '</span>') if tech else ''}</div>"
        desc = _tag("p", p.get("description", ""))
        proj_html += f"<div class='entry'>{header}{desc}{_bullets(p.get('highlights',[]))}</div>"

    def _section(title, body):
        if not body:
            return ""
        return f"<div class='section'><h2>{title}</h2>{body}</div>"

    links = ""
    if b.get("linkedin"):
        links += f" · <a href='{b['linkedin']}'>LinkedIn</a>"
    if b.get("github"):
        links += f" · <a href='{b['github']}'>GitHub</a>"
    if b.get("portfolio"):
        links += f" · <a href='{b['portfolio']}'>Portfolio</a>"

    contact = f"{b.get('email','')} · {b.get('phone','')} · {b.get('location','')}{links}".strip(" ·")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{b.get('name','Resume')}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; font-size: 11px; color: #111; max-width: 800px; margin: 0 auto; padding: 40px; }}
  h1 {{ font-size: 20px; margin-bottom: 2px; }}
  h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #ccc; padding-bottom: 3px; margin: 16px 0 8px; }}
  .contact {{ font-size: 10px; color: #444; margin-bottom: 4px; }}
  .contact a {{ color: #444; }}
  .summary {{ margin: 10px 0; line-height: 1.5; }}
  .section {{ margin-bottom: 8px; }}
  .entry {{ margin-bottom: 10px; }}
  .row {{ display: flex; justify-content: space-between; }}
  ul {{ margin: 4px 0 0 18px; }}
  li {{ margin-bottom: 2px; line-height: 1.4; }}
  p {{ margin-top: 3px; line-height: 1.4; }}
  @media print {{
    body {{ padding: 20px; }}
    @page {{ margin: 1cm; }}
  }}
</style>
</head>
<body>
  <h1>{b.get('name','')}</h1>
  <div class="contact">{contact}</div>
  {('<p class="summary">' + b.get('summary','') + '</p>') if b.get('summary') else ''}
  {_section('Experience', exp_html)}
  {_section('Education', edu_html)}
  {_section('Skills', skills_html)}
  {_section('Projects', proj_html)}
</body>
</html>"""

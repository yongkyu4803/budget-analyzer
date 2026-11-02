#!/usr/bin/env python3
"""인덱스 문서 검사기 — 서식은 프로파일이 정하고, 검사 기계는 도메인을 모른다.

사용:
  python3 validate_index.py index/2024-Huffman.md
  python3 validate_index.py index/*.md
  python3 validate_index.py doc.md --profile research-paper
  python3 validate_index.py --show-profile research-paper

프로파일 해석 순서
  1) --profile 인자
  2) 문서 안의 마커  <!-- doc-index: profile=<이름> -->
  3) 실패 — 어느 서식으로 검사해야 할지 추측하지 않는다

프로파일 탐색 경로
  <문서기준 워크스페이스>/.doc-index/profiles/<이름>.md   (워크스페이스 재정의)
  <이 스크립트>/../profiles/<이름>.md                      (기본 제공)

종료코드 0=통과, 1=실패.

설계 원칙 — 이 검사기가 보는 것은 **형식**이다. 값이 원문과 같은지는 보지 못한다.
그래서 negative_control.py 로 "일부러 틀린 문서를 실제로 잡는지"를 함께 검사한다.
검사를 새로 추가하면 negative_control.py 에 대응 변이를 반드시 추가할 것.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import miniyaml  # 표준 라이브러리만 — 네트워크가 막힌 환경에서도 검사가 돌아야 한다

HERE = Path(__file__).resolve().parent
BUILTIN_PROFILES = HERE.parent / "profiles"

MARKER = re.compile(r"<!--\s*doc-index:\s*profile\s*=\s*([A-Za-z0-9_.-]+)", re.I)
DOC_FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)
FM_MARKER = re.compile(r"^doc-index-profile:\s*([A-Za-z0-9_.-]+)\s*$", re.M)


def doc_frontmatter(text):
    """인덱스 문서 자신의 YAML 머리말. 없으면 None."""
    m = DOC_FM.match(text)
    return m.group(1) if m else None


def profile_of(text):
    """프로파일 이름을 찾는다. 프론트매터가 먼저, 없으면 HTML 주석(하위 호환)."""
    fm = doc_frontmatter(text)
    if fm:
        m = FM_MARKER.search(fm)
        if m:
            return m.group(1)
    m = MARKER.search(text)
    return m.group(1) if m else None
PLACEHOLDER = re.compile(r"\{\{.*?\}\}")
TEMPLATE_COMMENT = re.compile(r"^\s*//", re.M)
HANGUL = re.compile(r"[가-힣]")
# 구간추정: (a, b) / (a ~ b) / (a to b) / (a–b) — 음수 부호와 각종 대시를 허용
INTERVAL = re.compile(
    r"[(\[]\s*[−–—+-]?\d[\d.,]*\s*(?:,|~|틸|to|–|—|-)\s*[−–—+-]?\d"
    r"|95%\s*CI\s*[:=]?\s*[−–—+-]?\d"
)
NUMERIC = re.compile(r"\d")
# 빈칸 때우기: 완전 공백이거나 대시·물결·마침표만 있는 셀
FILLER_CELL = re.compile(r"^(?:[\s\-–—~.·]*|[Nn]/?[Aa]|[Nn][Aa])$")


# ---------------------------------------------------------------- 문서 구조

def split_sections(text):
    """'## <n>. 제목' 단위로 자른다. -> [(번호, 제목, 본문)]"""
    heads = list(re.finditer(r"^##\s+(\d+)\.\s*(.+?)\s*$", text, re.M))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        out.append((m.group(1), m.group(2), text[m.end():end]))
    return out


def cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def tables(body):
    """본문에서 표를 뽑는다. -> [{'header':[...], 'rows':[(줄번호, [셀…])]}]"""
    lines = body.splitlines()
    found = []
    i = 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith("|") and re.match(r"^\s*\|[\s:|-]+\|?\s*$", lines[i + 1]):
            header = cells(lines[i])
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append((j, cells(lines[j])))
                j += 1
            found.append({"header": header, "rows": rows})
            i = j
        else:
            i += 1
    return found


# ---------------------------------------------------------------- 프로파일

def find_workspace(doc: Path):
    """문서에서 위로 올라가며 .doc-index/ 또는 index/ 를 가진 디렉터리를 찾는다."""
    for d in [doc.resolve().parent, *doc.resolve().parents]:
        if (d / ".doc-index").is_dir() or (d / "index").is_dir():
            return d
    return None


def load_profile(name, doc: Path):
    candidates = []
    ws = find_workspace(doc)
    if ws:
        candidates.append(ws / ".doc-index" / "profiles" / f"{name}.md")
    candidates.append(BUILTIN_PROFILES / f"{name}.md")
    for p in candidates:
        if p.is_file():
            raw = p.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
            if not m:
                raise SystemExit(f"프로파일에 YAML 머리말이 없습니다: {p}")
            try:
                return miniyaml.load(m.group(1)) or {}, p
            except miniyaml.MiniYamlError as e:
                raise SystemExit(f"프로파일 머리말을 읽지 못했습니다: {p}\n  {e}")
    tried = "\n  ".join(str(c) for c in candidates)
    raise SystemExit(f"프로파일 '{name}'을 찾지 못했습니다. 찾아본 곳:\n  {tried}")


# ---------------------------------------------------------------- 검사 본체

class Report:
    def __init__(self):
        self.fails, self.warns = [], []

    def fail(self, msg):
        self.fails.append(msg)

    def warn(self, msg):
        self.warns.append(msg)


def satisfied(value, rule, unreported):
    if any(tok in value for tok in unreported):
        return True
    if rule == "interval":
        return bool(INTERVAL.search(value))
    if rule == "numeric":
        return bool(NUMERIC.search(value))
    if rule == "nonempty":
        return not FILLER_CELL.match(value)
    raise SystemExit(f"프로파일 오류: 알 수 없는 require '{rule}'")


RULE_KO = {"interval": "구간추정(95% CI 등)이", "numeric": "수치가", "nonempty": "내용이"}


def check(path, forced_profile=None, origin=None):
    """origin: 프로파일 탐색의 기준 경로. 변이 문서처럼 원래 워크스페이스 밖에
    놓인 사본을 검사할 때, 워크스페이스 전용 프로파일을 계속 찾을 수 있게 한다."""
    doc = Path(path)
    text = doc.read_text(encoding="utf-8")
    r = Report()

    name = forced_profile or profile_of(text)
    if not name:
        r.fail("프로파일 마커가 없습니다 — 문서 머리말에 doc-index-profile: <이름> 을 "
               "넣거나(권장) <!-- doc-index: profile=<이름> --> 를 쓰거나 --profile 로 지정하세요")
        return r, None
    prof, prof_path = load_profile(name, Path(origin) if origin else doc)

    unreported = prof.get("unreported_tokens", ["원문 미보고"])
    secs = split_sections(text)
    by_num = {n: (t, b) for n, t, b in secs}

    # --- 1. 절 구조 (프로파일이 선언한 순서 그대로)
    want = prof.get("sections", [])
    if want:
        got_nums = [n for n, _, _ in secs]
        want_nums = [str(s["n"]) for s in want]
        if got_nums != want_nums:
            r.fail(f"절 구조: {want_nums} 여야 하는데 {got_nums}")
        else:
            for s in want:
                title = by_num[str(s["n"])][0]
                if s["title"] not in title:
                    r.warn(f"{s['n']}절 제목이 서식과 다름: '{title}' (기대: …{s['title']}…)")

    # --- 2. 분량
    if lim := prof.get("length"):
        measured = DOC_FM.sub("", text, count=1)      # 머리말은 서술이 아니다
        body_wo_tables = re.sub(r"^\s*\|.*$", "", measured, flags=re.M)
        narrative = len(re.sub(r"\s+", "", body_wo_tables))
        total = len(re.sub(r"\s+", "", measured))
        for key, val, label in (("narrative", narrative, "서술부(표 제외)"),
                                ("total", total, "전체")):
            if key in lim:
                lo, hi = lim[key]
                if not lo <= val <= hi:
                    r.fail(f"분량: {label} {val:,}자 — 기준 {lo:,}~{hi:,}자")

    # --- 3. 프로파일이 선언한 검사들
    for c in prof.get("checks", []):
        kind = c.get("kind")

        if kind == "table_columns":
            sec = str(c["section"])
            if sec not in by_num:
                r.fail(f"{sec}절이 없어 표 검사를 못 했습니다")
                continue
            hit = 0
            for tb in tables(by_num[sec][1]):
                for spec in c["columns"]:
                    idx = next((j for j, h in enumerate(tb["header"])
                                if re.search(spec["match"], h, re.I)), None)
                    if idx is None:
                        continue
                    hit += 1
                    for lineno, cs in tb["rows"]:
                        if idx >= len(cs):
                            r.fail(f"{sec}절 표: 열 수가 머리글과 다릅니다 (행: {cs[0][:30] if cs else '?'})")
                            continue
                        v = cs[idx]
                        if not satisfied(v, spec["require"], unreported):
                            label = cs[0][:40] if cs else "?"
                            r.fail(f"{sec}절 '{label}': "
                                   f"'{tb['header'][idx]}' 열에 {RULE_KO[spec['require']]} 없음 → '{v}'")
            if not hit:
                cols = " / ".join(s["match"] for s in c["columns"])
                r.fail(f"{sec}절: 검사 대상 열({cols})을 가진 표를 찾지 못함")

        elif kind == "min_rows":
            sec = str(c["section"])
            n = sum(len(tb["rows"]) for tb in tables(by_num.get(sec, ("", ""))[1]))
            if n < c["min"]:
                r.fail(f"{sec}절: {c.get('label', '항목')} {n}개 — 최소 {c['min']}개 필요")

        elif kind == "verbatim_quotes":
            sec = str(c["section"])
            body = by_num.get(sec, ("", ""))[1]
            qs = re.findall(r'"([^"]{%d,})"' % c.get("min_chars", 30), body)
            if len(qs) < c["min"]:
                r.fail(f"{sec}절: 원문 인용 {len(qs)}개 — {c['min']}개 필요")
            if c.get("forbid_hangul", True):
                for q in qs:
                    if HANGUL.search(q):
                        r.fail(f"{sec}절: 한국어가 섞인 인용문 → \"{q[:50]}…\" "
                               "(번역문은 인용이 아니라 해석이다)")

        elif kind == "badge_consistency":
            badge, marker = c["badge"], c["marker"]
            has_badge, has_marker = badge in text, marker in text
            if has_badge and not has_marker:
                r.warn(f"'{badge}' 배지가 있는데 '{marker}' 표기가 한 곳도 없음")
            if not has_badge and has_marker:
                r.fail(f"'{marker}'를 썼는데 상단 '{badge}' 배지가 없음")

        elif kind == "required_text":
            if c["text"] not in text:
                r.fail(f"필수 문구 누락: '{c['text']}'")

        else:
            raise SystemExit(f"프로파일 오류: 알 수 없는 kind '{kind}' ({prof_path})")

    # --- 4. 도메인 무관 공통 검사 (프로파일이 끄지 못한다)
    if left := PLACEHOLDER.findall(text):
        r.fail(f"치환되지 않은 템플릿 자리 {len(left)}개: {left[:3]}")
    if TEMPLATE_COMMENT.search(text):
        r.fail("템플릿 작성 지침(// 주석)이 산출물에 남아 있음")

    # 빈칸·대시로 때운 셀 — '확인 안 함'과 '원문에 없음'을 구분하지 못하게 만든다
    for n, title, body in secs:
        for tb in tables(body):
            for _, cs in tb["rows"]:
                for j, v in enumerate(cs):
                    if FILLER_CELL.match(v):
                        head = tb["header"][j] if j < len(tb["header"]) else f"{j+1}번째 열"
                        label = cs[0][:30] if cs else "?"
                        r.fail(f"{n}절 '{label}': '{head}' 칸이 비어 있음 → "
                               f"{unreported[0]} 처럼 명시할 것")
    return r, prof_path


def main():
    ap = argparse.ArgumentParser(description="인덱스 문서 검사 (프로파일 구동)")
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--profile", help="문서의 마커 대신 이 프로파일로 검사")
    ap.add_argument("--show-profile", metavar="이름", help="프로파일 선언을 출력하고 종료")
    a = ap.parse_args()

    if a.show_profile:
        prof, p = load_profile(a.show_profile, Path.cwd() / "x.md")
        print(f"# {p}")
        print(json.dumps(prof, ensure_ascii=False, indent=2))
        return

    paths = [p for p in a.paths if not Path(p).name.startswith("_")]
    if not paths:
        sys.exit("사용: validate_index.py <인덱스.md> [...]   (_로 시작하는 파일은 제외)")

    bad = 0
    for p in paths:
        r, prof_path = check(p, a.profile)
        mark = "PASS" if not r.fails else "FAIL"
        tag = f" [{prof_path.stem}]" if prof_path else ""
        print(f"[{mark}] {Path(p).name}{tag}")
        for f in r.fails:
            print(f"   ✗ {f}")
        for w in r.warns:
            print(f"   ! {w}")
        bad += bool(r.fails)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

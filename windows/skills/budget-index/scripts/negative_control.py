#!/usr/bin/env python3
"""음성 대조 — 검사기가 '일부러 틀린 문서'를 실제로 잡는지 확인한다.

사용:
  python3 negative_control.py <통과하는_인덱스.md> [--profile 이름] [--keep]

왜 필요한가
  validate_index.py 는 형식만 본다. 형식 검사는 조용히 무력해질 수 있다 —
  전례: 결과표를 '행 단위'로 보던 검사기는 값을 "약간 감소" 같은 서술로
  바꿔치기해도 통과시켰다. 검사가 통과했다는 사실이 정확하다는 뜻으로
  읽히는 순간, 검사는 장식이 된다.

  변이는 **프로파일 선언에서 만들어진다.** 검사기와 같은 선언을 읽으므로,
  새 프로파일을 만들면 음성 대조가 따라온다 — 손으로 변이를 추가할 필요가 없다.

종료코드 0 = 모든 변이가 잡힘, 1 = 새어 나간 변이 있음.
"""
import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_index import check, load_profile, profile_of  # noqa: E402


# ------------------------------------------------------------------ 문서 도구

def sec_range(lines, n):
    start = next((i for i, l in enumerate(lines) if re.match(rf"^##\s+{n}\.", l)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^##\s+\d+\.", lines[i])), len(lines))
    return start, end


def is_sep(line):
    return bool(re.match(r"^\s*\|[\s:|-]+\|?\s*$", line))


def find_table(lines, lo, hi, header_pat):
    """머리글이 header_pat에 걸리는 표 -> (머리글줄, 첫 데이터줄, 끝+1, 열번호)"""
    for i in range(lo, hi - 1):
        if not (lines[i].lstrip().startswith("|") and is_sep(lines[i + 1])):
            continue
        cs = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        idx = next((j for j, c in enumerate(cs) if re.search(header_pat, c, re.I)), None)
        if idx is None:
            continue
        j = i + 2
        while j < hi and lines[j].lstrip().startswith("|") and not is_sep(lines[j]):
            j += 1
        if j > i + 2:
            return i, i + 2, j, idx
    return None


def set_cell(line, idx, value):
    cs = [c.strip() for c in line.strip().strip("|").split("|")]
    if idx >= len(cs):
        return None
    cs[idx] = value
    return "| " + " | ".join(cs) + " |"


def header_text(text, section, header_pat):
    """문서에서 실제 머리글 문구를 가져온다 — 라벨에 정규식 조각을 쓰지 않도록."""
    lines = text.splitlines()
    rng = sec_range(lines, section)
    if not rng:
        return None
    tb = find_table(lines, *rng, header_pat)
    if not tb:
        return None
    head, _, _, idx = tb
    cs = [c.strip() for c in lines[head].strip().strip("|").split("|")]
    return cs[idx]


def swap_cell(text, section, header_pat, value):
    lines = text.splitlines()
    rng = sec_range(lines, section)
    if not rng:
        return None
    tb = find_table(lines, *rng, header_pat)
    if not tb:
        return None
    _, first, _, idx = tb
    new = set_cell(lines[first], idx, value)
    if new is None or new == lines[first]:
        return None
    lines[first] = new
    return "\n".join(lines) + "\n"


def inject_line(text, payload, sections):
    """두 번째 절 바로 앞에 한 줄 심는다 (본문 어딘가면 된다)."""
    if len(sections) < 2:
        return None
    anchor = f"\n## {sections[1]['n']}."
    if anchor not in text:
        return None
    return text.replace(anchor, f"\n{payload}\n{anchor}", 1)


def drop_table_rows(text, section, keep):
    """해당 절 표의 데이터 행을 keep개만 남긴다."""
    lines = text.splitlines()
    rng = sec_range(lines, section)
    if not rng:
        return None
    lo, hi = rng
    data = [i for i in range(lo, hi)
            if lines[i].lstrip().startswith("|") and not is_sep(lines[i])]
    # 첫 줄은 머리글
    body = data[1:] if len(data) > 1 else []
    if len(body) <= keep:
        return None
    drop = set(body[keep:])
    return "\n".join(l for i, l in enumerate(lines) if i not in drop) + "\n"


def quotes_in(text, section, min_chars):
    lines = text.splitlines()
    rng = sec_range(lines, section)
    if not rng:
        return []
    lo, hi = rng
    return [(i, m.group(0)) for i in range(lo, hi)
            for m in [re.search(r'"[^"]{%d,}"' % min_chars, lines[i])] if m]


# ------------------------------------------------------------------ 변이 생성

PROSE = {"interval": "약간 감소", "numeric": "유의함"}
FILLERS = [("빈칸", ""), ("대시", "—"), ("N/A", "N/A")]


def build_mutations(prof, text, skipped=None):
    """프로파일 선언 -> [(라벨, 변이문서, 어느 검사를 겨냥하는가)]

    skipped: 리스트를 넘기면 '만들 수 없었던 변이'와 이유를 채운다.
    건너뛴 검사를 말하지 않으면, 안 한 검사와 통과한 검사가 같아 보인다."""
    out = []
    secs = prof.get("sections", [])

    def add(label, new, what, why="이 문서에 해당 요소가 없음"):
        if new and new != text:
            out.append((label, new, what))
        elif skipped is not None:
            skipped.append((label, what, why))

    for c in prof.get("checks", []):
        kind = c.get("kind")

        if kind == "table_columns":
            sec = c["section"]
            for spec in c["columns"]:
                pat, req = spec["match"], spec["require"]
                short = header_text(text, sec, pat) or pat[:12]
                if req in PROSE:
                    add(f"{sec}절 {short} → 서술로 바꿔치기",
                        swap_cell(text, sec, pat, PROSE[req]), f"{sec}절 {req} 열")
                for name, val in FILLERS:
                    add(f"{sec}절 {short} → {name}",
                        swap_cell(text, sec, pat, val), "빈칸 때우기")

        elif kind == "min_rows":
            sec, mn = c["section"], c["min"]
            add(f"{sec}절 {c.get('label','항목')} {mn-1}개로 줄이기",
                drop_table_rows(text, sec, mn - 1), f"{sec}절 최소 개수")

        elif kind == "verbatim_quotes":
            sec, mn = c["section"], c["min"]
            mc = c.get("min_chars", 30)
            qs = quotes_in(text, sec, mc)
            if len(qs) >= mn:
                lines = text.splitlines()
                drop = {i for i, _ in qs[mn - 1:]}
                add(f"{sec}절 인용 {mn-1}개로 줄이기",
                    "\n".join(l for i, l in enumerate(lines) if i not in drop) + "\n",
                    f"{sec}절 최소 개수")
            if c.get("forbid_hangul", True) and qs:
                i, q = qs[0]
                # 길이가 min_chars 미만이면 인용으로 인식되지 않아 '개수' 검사에
                # 먼저 걸린다. 그러면 한글 금지 규칙은 발동한 적이 없는데도
                # 잡힌 것처럼 보인다 — 반드시 길이를 넘겨 한글 규칙을 겨냥한다.
                ko = "저자들은 군간 차이가 통계적으로 유의하지 않았다고 보고하였다"
                while len(ko) < mc + 5:
                    ko += " 또한 하위군에서도 같은 경향이 관찰되었다고 한다"
                lines = text.splitlines()
                lines[i] = lines[i].replace(q, f'"{ko}"')
                add(f"{sec}절 인용을 번역문으로 교체",
                    "\n".join(lines) + "\n", f"{sec}절 원어 인용")

        elif kind == "required_text":
            add("필수 문구 삭제",
                re.sub(r"^.*" + re.escape(c["text"]) + r".*$", "", text,
                       count=1, flags=re.M),
                "required_text")

        elif kind == "badge_consistency":
            if c["badge"] not in text:
                add(f"배지 없이 '{c['marker']}'만 심기",
                    inject_line(text, f"이 항목은 {c['marker']}이다.", secs),
                    "배지 정합")
            elif skipped is not None:
                skipped.append((f"배지 없이 '{c['marker']}'만 심기", "배지 정합",
                                f"문서가 이미 '{c['badge']}' 배지를 달고 있어 변이가 성립하지 않음"))

    # --- 프로파일과 무관하게 언제나 적용되는 변이
    add("템플릿 자리 잔존", inject_line(text, "{{미기입 — 나중에 채울 것}}", secs),
        "공통: 플레이스홀더")
    add("작성 지침 주석 잔존", inject_line(text, "// 이 절은 3줄로 압축한다", secs),
        "공통: // 주석")
    if len(secs) >= 2:
        a, b = secs[0]["n"], secs[1]["n"]
        t2 = re.sub(rf"^##\s+{a}\.", "## §A§.", text, count=1, flags=re.M)
        t2 = re.sub(rf"^##\s+{b}\.", f"## {a}.", t2, count=1, flags=re.M)
        t2 = t2.replace("## §A§.", f"## {b}.", 1)
        add("절 순서 뒤바꿈", t2, "절 구조")
    add("서술부 걷어내기",
        "\n".join(l for l in text.splitlines()
                  if l.lstrip().startswith(("|", "#", "<!--", "*")) or not l.strip()) + "\n",
        "분량 하한")
    return out


# --------------------------------------------- 사각지대 (통과해야 정상)
# 형식 검사로는 원리상 볼 수 없는 것들. '검사 통과'가 '정확함'이 아님을
# 매 실행마다 눈에 보이게 하려고 넣는다.

def build_blind_spots(prof, text):
    out = []
    for c in prof.get("checks", []):
        if c.get("kind") != "table_columns":
            continue
        for spec in c["columns"]:
            if spec["require"] == "interval":
                out.append(("수치만 틀린 값",
                            swap_cell(text, c["section"], spec["match"],
                                      "MD −9.99 (−99.9 ~ 9.9)"),
                            "값이 원문과 같은지는"))
            elif spec["require"] == "numeric":
                out.append(("p값만 틀림",
                            swap_cell(text, c["section"], spec["match"], "0.999"),
                            "값이 원문과 같은지는"))
            elif spec["require"] == "nonempty":
                out.append(("형식은 멀쩡한 채 값만 틀림",
                            swap_cell(text, c["section"], spec["match"], "99.9 mm"),
                            "값이 원문과 같은지는"))
            break
    for c in prof.get("checks", []):
        if c.get("kind") == "min_rows":
            lines = text.splitlines()
            rng = sec_range(lines, c["section"])
            if rng:
                for i in range(*rng):
                    if re.search(r"(Table|Figure|표|그림|§|제)\s*\d", lines[i]):
                        L = lines[:]
                        L[i] = re.sub(r"\d+", "97", L[i], count=1)
                        out.append(("원문 위치가 틀림", "\n".join(L) + "\n",
                                    "포인터가 실재하는지는"))
                        break
            break
    out.append(("관찰을 인과로 서술",
                inject_line(text, "따라서 이 개입이 결과의 원인이다.",
                            prof.get("sections", [])),
                "논증의 타당성은"))
    return [(a, b, c) for a, b, c in out if b and b != text]


# ------------------------------------------------------------------ 실행

def run(baseline: Path, profile, keep):
    base_text = baseline.read_text(encoding="utf-8")
    name = profile or profile_of(base_text)
    if not name:
        print(f"[중단] 프로파일을 알 수 없습니다 — 마커가 없고 --profile도 없습니다: {baseline}")
        return 1
    prof, prof_path = load_profile(name, baseline)

    r, _ = check(baseline, profile)
    if r.fails:
        print(f"[중단] 기준 문서가 이미 실패합니다 — 먼저 통과시키세요: {baseline}")
        for f in r.fails:
            print(f"   ✗ {f}")
        return 1
    print(f"[양성 대조] {baseline.name} → PASS  ({prof_path.stem} 프로파일)")
    print("           기준이 통과하므로 아래 변이 결과를 해석할 수 있다.\n")

    tmp = Path(tempfile.mkdtemp(prefix="negctl-"))
    caught = leaked = 0
    skipped = []
    muts = build_mutations(prof, base_text, skipped)
    for label, mutated, what in muts:
        p = tmp / (re.sub(r"\W+", "_", label) + ".md")
        p.write_text(mutated, encoding="utf-8")
        rr, _ = check(p, profile, origin=baseline)
        if rr.fails:
            print(f"  ✓  {label:<34} 잡힘 — {rr.fails[0][:64]}")
            caught += 1
        else:
            print(f"  ✗  {label:<34} **새어 나감** ← '{what}' 검사가 장식이다")
            print(f"        재현: python3 validate_index.py {p}")
            leaked += 1

    print(f"\n변이 {len(muts)}개 · 잡힘 {caught} · 새어 나감 {leaked}")
    if skipped:
        print(f"\n만들지 못한 변이 {len(skipped)}개 — **검사한 것이 아니다**:")
        for label, what, why in skipped:
            print(f"  ―  {label:<34} {why}")
            print(f"     → '{what}' 검사는 이 문서로 확인되지 않았다")

    print("\n검사기가 못 보는 것 (통과하는 것이 정상 — 사람이 확인해야 한다):")
    for label, mutated, what in build_blind_spots(prof, base_text):
        p = tmp / ("blind_" + re.sub(r"\W+", "_", label) + ".md")
        p.write_text(mutated, encoding="utf-8")
        rr, _ = check(p, profile, origin=baseline)
        state = "그대로 통과" if not rr.fails else "우연히 걸림"
        print(f"  ⚠  {label:<24} {state} → {what} 검사기 밖이다")

    if keep or leaked:
        print(f"\n변이 문서: {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if leaked else 0


def main():
    ap = argparse.ArgumentParser(description="검사기가 틀린 문서를 실제로 잡는지 확인")
    ap.add_argument("baseline", help="현재 검사를 통과하는 인덱스 문서")
    ap.add_argument("--profile")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    sys.exit(run(Path(a.baseline), a.profile, a.keep))


if __name__ == "__main__":
    main()

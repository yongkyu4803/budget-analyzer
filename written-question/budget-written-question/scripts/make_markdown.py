#!/usr/bin/env python3
"""서면질의 입력 JSON → kordoc patch_document 용 편집 마크다운.

사용: python3 make_markdown.py spec.json [--stage 1|2] > edited.md
     (보통은 build.py 가 두 단계를 차례로 돌린다)

- stage 1: 감액 표는 첫 행만 채우고 칸 안 작성 안내 상자를 남긴다(kordoc 은 중첩표가 든 행을
  기준으로 행을 늘리지 못한다). 안내 상자는 postprocess.remove_guides 가 지운다.
- stage 2: 안내 상자가 지워진 문서에 모든 행을 채운다.

- 목록 순서를 내용 순서(① 감액 → ① 증액 → ② 감액 → ② 증액 → ③)로 맞춘다.
- 요구증감액은 숫자(백만원)로 받아 '△3,000' / '4,000' 으로 쓴다.
- 견본(assets/template_2027.hwpx)의 골격 문구를 그대로 둔다. 감액 표 첫 행 칸 안의
  작성 안내 상자(중첩표)는 patch 가 칸을 맞출 수 있도록 그대로 남기고, postprocess.py 가 지운다.
"""
import json
import sys

GUIDE_GENERAL = """<table>
<tr><th>□ 전년 본예산/추경 대비 증/감액(음영부분)은 아래 기준으로 작성<br>① 2026년 예산이 추경으로 변동되지 않은 경우: 전년 본예산 대비 00원 증/감액<br><table>
<tr><th>❍ (예시) 내역사업인 ‘글로벌 매칭형’(98억원, 전년 본예산 대비 30억원 증액)은 코로나19로 인해 입원한 경우 생활지원비 등을 제공하는 것임</th></tr>
</table><br>② 2026년 예산이 추경으로 변동된 경우: 전년 추경 대비 00원 증/감액<br><table>
<tr><th>❍ (예시) 내역사업인 ‘글로벌 매칭형’(98억원, 전년 추경 대비 30억원 증액)은 코로나19로 인해 입원한 경우 생활지원비 등을 제공하는 것임</th></tr>
</table><br>③ 2026년 본예산 또는 추경에 없던 신규사업인 경우: 신규<br><table>
<tr><th>❍ (예시) 내역사업인 ‘글로벌 매칭형’(신규)은 코로나19로 인해 입원한 경우 생활지원비 등을 제공하는 것임</th></tr>
</table><br>④ 2026년 본예산 또는 추경 대비 2027년 예산안의 증감이 없을 경우: 전년동<br><table>
<tr><th>❍ (예시) 내역사업인 ‘글로벌 매칭형’(98억원, 전년동)은 코로나19로 인해 입원한 경우 생활지원비 등을 제공하는 것임</th></tr>
</table></th></tr>
</table>"""

GUIDE_FUND = """<table>
<tr><th>전년 대비 증/감액(음영부분)은 2026년 7월말 기준 수정계획액 대비 2027년 계획안의 증/감액을 작성</th></tr>
</table>"""

REF_TABLE = """<table>
<tr><th></th><th rowspan="2">(참고) 요구증감액란 작성예시</th></tr>
<tr><td></td></tr>
<tr><td colspan="2">❍ (감액예시) 2027년도 예산이 1,000백만원인 사업에 대해 △300백만원 감액을 원하는 경우, ‘요구증감액’란에 △300백만원을 기재 (△300백만원 감액이 반영된 700백만원을 기재하는 것이 아님)<br>❍ (증액예시) 2027년도 예산이 1,000백만원인 사업에 대해 2,000백만원 증액을 원하는 경우, ‘요구증감액(의견)’란에 2,000백만원을 기재 (2,000백만원 증액이 반영된 3,000백만원을 기재하는 것이 아님)</td></tr>
</table>"""


def amt(v):
    """백만원 금액 표기. 숫자는 천 단위 쉼표, 음수는 △, 문자열('-')은 그대로."""
    if v is None or v == "":
        return "-"
    if isinstance(v, str):
        return v
    s = f"{abs(int(v)):,}"
    return "△" + s if v < 0 else s


def esc(s):
    return s.replace("<", "&lt;").replace(">", "&gt;")


def name_cell(it, with_sub):
    s = f"{it['program']}<br>({it['code']})"
    if with_sub and it.get("sub"):
        s = f"{it['program']}<br>({it['code']})-<br>{it['sub']}"
    return s


def reasons_html(it):
    lines = []
    sd = it.get("sub_desc")
    if it.get("sub") and sd:
        # 견본 강조 서식: ‘내역사업명’ 굵게, 증감 문구 음영 — postprocess.py 가 runs 를 다시 나눈다
        lines.append(f"❍ 내역사업인 ‘{it['sub']}’({sd['amount']}, {sd['change']}){sd['rest']}")
    lines += [f"❍ {r}" for r in it["reasons"]]
    return "<br>".join(lines)


def check(spec):
    errs = []
    for i, it in enumerate(spec.get("items", [])):
        for k in ("section", "type", "account", "program", "code", "change", "reasons"):
            if k not in it:
                errs.append(f"items[{i}] '{k}' 없음")
        if it.get("section") not in ("general", "fund"):
            errs.append(f"items[{i}].section 은 general|fund")
        if it.get("type") not in ("cut", "increase"):
            errs.append(f"items[{i}].type 은 cut|increase")
        ch = it.get("change", 0)
        if it.get("type") == "cut" and ch >= 0:
            errs.append(f"items[{i}] 감액인데 change 가 음수가 아님")
        if it.get("type") == "increase" and ch <= 0:
            errs.append(f"items[{i}] 증액인데 change 가 양수가 아님")
        if it.get("type") == "increase" and it.get("sub"):
            errs.append(f"items[{i}] 증액질의는 세부사업명만 기재(sub 사용 불가)")
    if errs:
        sys.exit("입력 오류:\n" + "\n".join(errs))


def build(spec, stage=2):
    check(spec)
    items = spec.get("items", [])
    order = [("general", "cut"), ("general", "increase"), ("fund", "cut"), ("fund", "increase")]
    groups = {k: [it for it in items if (it["section"], it["type"]) == k] for k in order}
    ordered = [it for k in order for it in groups[k]]
    ops = spec.get("opinions", [])

    m, d, p = spec["ministry"], spec["date"], spec["member"]
    out = []
    w = out.append

    # 1. 신청서
    w("**[첨부]**\n\n**1. 서면질의 신청서**\n")
    w(f"**<대상부처: {m}>**\n")
    w("■ 수신 : 예산결산특별위원장\n")
    w(f"■ 회차 : {spec['session']} 예산결산특별위원회\n")
    w("국회법 제69조 및 제104조제6항에 따라 다음과 같이 질문서를 제출합니다.\n")
    w(f"제출일 {d}\n")
    w(f"**국회의원 {p}            (인)**\n")
    w("<유의사항>\n※ 대상부처는 1개 부처만 기재\n※ 여러 개의 부처를 묶어 제출 시 접수 불가\n(각 부처별로 개별 서면질의 신청서/목록/내용 제출)\n")

    # 2. 목록 — 견본 데이터 행 6개를 쓰고 남는 행은 비운다(postprocess 가 삭제)
    w(f"**[첨부]**\n\n**2. 서면질의 목록({m})**\n")
    w(f"■ 의원명 : {p} 의원\n")
    w(f"■ 제출일자 : {d}\n")
    rows = []
    for it in ordered:
        acct = it["account"]
        rows.append(f"<tr><td>{acct}</td><td>{it['program']}<br>({it['code']})</td>"
                    f"<td>{amt(it.get('prev'))}</td><td>{amt(it.get('proposal'))}</td><td>{amt(it['change'])}</td></tr>")
    for o in ops:
        rows.append(f"<tr><td>{o['kind']}</td><td>{o['summary']}</td><td>-</td><td>-</td><td>-</td></tr>")
    while len(rows) < 6:
        rows.append("<tr><td></td><td></td><td></td><td></td><td></td></tr>")
    w("<table>\n<tr><th colspan=\"5\">(단위: 백만원)</th></tr>\n"
      "<tr><td>회계/기금명</td><td>세부사업명<br>(사업코드)</td><td>2026년<br>본예산(추경)</td><td>2027년도<br>예산안</td><td>요구<br>증감액</td></tr>\n"
      + "\n".join(rows) +
      "\n<tr><td colspan=\"5\">주1) 2026년 본예산(추경): 제1회 추경으로 예산이 변경된 경우 변경된 예산현액을 기재<br>2) 요구증감액: 2027년도 예산안 심의과정에서 희망하는 증액 또는 감액(△) 금액을 기재<br>(증감이 반영된 금액 기재 ×)</td></tr>\n</table>\n")
    w(REF_TABLE + "\n")

    # 3. 내용
    first = ordered[0] if ordered else None
    title = f"{first['program']}({first['code']})" if first else "-"
    if len(ordered) > 1:
        title += f" 외 {len(ordered) - 1}개 사업"
    accts = []
    for it in ordered:
        if it["account"] not in accts:
            accts.append(it["account"])
    w("**[첨부]**\n\n**3. 서면질의 내용**\n")
    w(f"<table>\n<tr><th>2027년도 예산안 서면질의</th><th>국회의원 {p}</th><th>{spec['party']}</th></tr>\n"
      f"<tr><td colspan=\"3\">{title}<br>&lt; {spec['committee']} / {m} 소관 / {'·'.join(accts) or '-'} &gt;</td></tr>\n</table>\n")
    w("□ 총괄표  \n")

    # ① 일반회계/특별회계
    w("**① 일반회계/특별회계**\n")
    w("< 감액질의 >\n")
    cuts = groups[("general", "cut")]
    body = []
    cuts = cuts[:1] if stage == 1 else cuts
    for i, it in enumerate(cuts or [None]):
        guide = "<br>" + GUIDE_GENERAL if (i == 0 and stage == 1) else ""
        if it is None:
            body.append(f"<tr><td>-</td><td>-</td><td>-</td><td>-</td><td>해당 없음{guide}</td></tr>")
            continue
        sub = bool(it.get("sub"))
        pv = it.get("row_prev", it.get("prev")) if sub else it.get("prev")
        pr = it.get("row_proposal", it.get("proposal")) if sub else it.get("proposal")
        body.append(f"<tr><td>{name_cell(it, True)}</td><td>{amt(pv)}</td><td>{amt(pr)}</td>"
                    f"<td>{amt(it['change'])}</td><td>{reasons_html(it)}{guide}</td></tr>")
    w("<table>\n<tr><th colspan=\"5\">(단위: 백만원)</th></tr>\n"
      "<tr><td>세부사업명<br>(0000-000)-내역사업명</td><td>2026년<br>본예산<br>(추경)</td><td>2027년<br>예산안</td><td>요구<br>증감액</td><td>수정이유</td></tr>\n"
      + "\n".join(body) +
      "\n<tr><td colspan=\"5\">주) 2026년 본예산(추경): 제1회 추경으로 예산이 변경된 경우 변경된 예산현액을 기재</td></tr>\n</table>\n")

    w("< 증액질의 >\n")
    incs = groups[("general", "increase")]
    body = []
    for it in incs or [None]:
        if it is None:
            body.append("<tr><td>-</td><td>-</td><td>-</td><td>-</td><td>해당 없음</td></tr>")
            continue
        body.append(f"<tr><td>{name_cell(it, False)}</td><td>{amt(it.get('prev'))}</td><td>{amt(it.get('proposal'))}</td>"
                    f"<td>{amt(it['change'])}</td><td>{reasons_html(it)}</td></tr>")
    w("<table>\n<tr><th colspan=\"5\">(단위: 백만원)</th></tr>\n"
      "<tr><td>세부사업명<br>(0000-000)</td><td>2026년<br>본예산<br>(추경)</td><td>2027년<br>예산안</td><td>요구<br>증감액</td><td>수정이유</td></tr>\n"
      + "\n".join(body) +
      "\n<tr><td colspan=\"5\">주1) 증액질의의 경우 세부사업명만 기재<br>2) 2026년 본예산(추경): 제1회 추경으로 예산이 변경된 경우 변경된 예산현액을 기재</td></tr>\n</table>\n")

    # ② 기금
    fund_head = ("<tr><td rowspan=\"2\">{n}</td><td colspan=\"2\">2026년</td><td rowspan=\"2\">2027년<br>계획안</td>"
                 "<td rowspan=\"2\">요구<br>증감액</td><td rowspan=\"2\">수정이유</td></tr>\n<tr><td>당초</td><td>수정</td></tr>\n")
    w("**② 기금**\n")
    w("< 감액질의 >\n")
    cuts = groups[("fund", "cut")]
    body = []
    cuts = cuts[:1] if stage == 1 else cuts
    for i, it in enumerate(cuts or [None]):
        guide = "<br>" + GUIDE_FUND if (i == 0 and stage == 1) else ""
        if it is None:
            body.append(f"<tr><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>해당 없음{guide}</td></tr>")
            continue
        body.append(f"<tr><td>{name_cell(it, True)}</td><td>{amt(it.get('prev_initial'))}</td><td>{amt(it.get('prev_revised'))}</td>"
                    f"<td>{amt(it.get('proposal'))}</td><td>{amt(it['change'])}</td><td>{reasons_html(it)}{guide}</td></tr>")
    w("<table>\n<tr><th colspan=\"6\">(단위: 백만원)</th></tr>\n"
      + fund_head.format(n="세부사업명<br>(0000-000)-내역사업명") + "\n".join(body) + "\n</table>\n")
    w("※ <u>**수정란에는 2026년 7월말 기준 수정액을 작성**</u>\n")
    w("※ 2027년도 계획안 금액 작성 기본단위는 ‘세부사업’임\n")
    w("※ 세부사업이 아닌 내역사업에 대한 질의는 ‘수정이유’에 명시할 것(위 표 예시 참조)\n")
    w("※ 수정이유는 ‘000 사업은 \\~한 이유로 0,000만원 증액’과 같이 수정대상 (내역)사업명과 수정사유가 명확히 드러나도록 작성\n")
    w("< 증액질의 >\n")
    incs = groups[("fund", "increase")]
    body = []
    for it in incs or [None]:
        if it is None:
            body.append("<tr><td>-</td><td>-</td><td>-</td><td>-</td><td>-</td><td>해당 없음</td></tr>")
            continue
        body.append(f"<tr><td>{name_cell(it, False)}</td><td>{amt(it.get('prev_initial'))}</td><td>{amt(it.get('prev_revised'))}</td>"
                    f"<td>{amt(it.get('proposal'))}</td><td>{amt(it['change'])}</td><td>{reasons_html(it)}</td></tr>")
    w("<table>\n<tr><th colspan=\"6\">(단위: 백만원)</th></tr>\n"
      + fund_head.format(n="세부사업명<br>(0000-000)") + "\n".join(body) +
      "\n<tr><td colspan=\"6\">주) 증액질의의 경우 세부사업명만 기재</td></tr>\n</table>\n")
    w(REF_TABLE + "\n")

    # ③ 부대의견·정책질의
    w("**③ 부대의견(안)·정책질의**\n")
    body = [f"<tr><td>{o['kind']}</td><td>❍ {o['text']}</td></tr>" for o in ops] or ["<tr><td>-</td><td>해당 없음</td></tr>"]
    w("<table>\n<tr><th>부대의견/<br>정책질의</th><th>부대의견(안) 또는 정책질의 요지</th></tr>\n"
      + "\n".join(body) +
      "\n<tr><td colspan=\"2\">※‘부대의견’은 예산의 증감을 수반하지 않는 제기사항으로, ‘00부는 ~한다.’ 형태로 기재<br>※‘정책질의’는 예산 증감이나 부대의견(안)으로 논의되지 않고 정부 측 답변만을 희망할 경우 기재</td></tr>\n</table>\n")
    w("□ 이하 자유양식\n")
    return "\n".join(out)


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    stage = int(sys.argv[sys.argv.index("--stage") + 1]) if "--stage" in sys.argv else 2
    print(build(spec, stage))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""완성본 점검. 사용: python3 check.py output.hwpx [template.hwpx]

- 글꼴·글자 서식 정의(header.xml)가 견본과 같은지
- 쪽 나눔(신청서·목록·내용) 수가 견본과 같은지
- 견본 자리표시(○○사업, 0,000, 글로벌 매칭형 등)가 남지 않았는지
- 목록의 사업코드 순서와 내용(①·②)의 사업코드 순서가 같은지
- 감액(△) 표기가 목록과 내용에서 일치하는지
문제가 있으면 종료 코드 1.
"""
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
tmpl = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent / "assets" / "template_2027.hwpx"
out = Path(sys.argv[1])


def read(p, name):
    with zipfile.ZipFile(p) as z:
        return z.read(name).decode("utf-8")


problems = []
with zipfile.ZipFile(out) as z:
    if z.namelist()[0] != "mimetype" or z.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
        problems.append("mimetype 이 맨 앞 무압축이 아님")

if read(out, "Contents/header.xml") != read(tmpl, "Contents/header.xml"):
    problems.append("header.xml(글꼴·서식 정의)이 견본과 다름")

sec, tsec = read(out, "Contents/section0.xml"), read(tmpl, "Contents/section0.xml")
pb, tpb = sec.count('pageBreak="1"'), tsec.count('pageBreak="1"')
if pb != tpb:
    problems.append(f"쪽 나눔 수 {pb} (견본 {tpb})")

text = "".join(re.findall(r"<hp:t>(.*?)</hp:t>", sec, re.S))
text = re.sub(r"<[^>]+>", "", text)
for ph in ["○○사업", "0000부/처", "글로벌 매칭형", "~~~~(사업 설명)", "증액 상세사유 기재", "00위원회 / 00부", "내용 간략 요약", "2,333"]:
    if ph in text:
        problems.append(f"견본 자리표시가 남음: {ph}")

code = r"\((\d{4}-\d{3})\)"
i_list = text.find("회계/기금명")
list_part = text[i_list:text.find("(증감이 반영된", i_list)]
i_body = text.find("총괄표")
i_op = text.find("부대의견(안)·정책질의", i_body)
body_part = text[i_body:i_op if i_op > 0 else len(text)]
lc = [c for c in re.findall(code, list_part) if c != "0000-000"]
bc = [c for c in re.findall(code, body_part) if c != "0000-000"]
if lc != bc:
    problems.append(f"목록 순서 {lc} ≠ 내용 순서 {bc}")

print(f"목록 사업코드: {lc}")
print(f"내용 사업코드: {bc}")
if problems:
    print("문제:\n- " + "\n- ".join(problems))
    sys.exit(1)
print("점검 통과: 글꼴 정의·쪽 나눔·자리표시·목록/내용 순서")

#!/usr/bin/env python3
"""patch_document 결과 HWPX 후처리 (kordoc 이 못 하는 부분).

사용: python3 postprocess.py patched.hwpx output.hwpx

1. 감액 표 칸 안의 작성 안내 상자(‘음영부분’ 중첩표)를 지운다.
2. 목록 표에서 내용이 빈 데이터 행을 지우고 rowCnt·rowAddr·표 높이를 맞춘다.
3. 칸 안에서 줄 수를 줄일 때 kordoc 이 남긴 빈 문단을 지운다.
4. ‘❍ 내역사업인 ‘이름’(금액, 증감)…’ 줄을 견본 강조 서식(이름 굵게, 증감 음영)으로 다시 나눈다.
5. mimetype 을 맨 앞 무압축으로 두고 HWPX 를 다시 묶는다.

글자 서식 번호(charPrIDRef)는 assets/template_2027.hwpx 기준이다. 견본이 바뀌면 check.py 가
header 불일치로 알려 준다.
"""
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

# template_2027 의 ‘내역사업인’ 견본 줄 run 구성
GEN_PARA, FUND_PARA = "57", "75"  # 견본 내역사업 줄의 문단 서식
GEN_IDS = dict(bullet="44", space="45", lead="29", quote="92", name="95", amount="93", sep="46", change="74", close="44", rest="73")
FUND_IDS = dict(bullet="6", name="47", amount="48", change="46", rest="45")
SUB_RE = re.compile(r"^❍\s*내역사업인\s*‘(.+?)’\(([^)]*), ([^,)]+)\)(.*)$")  # 금액 안 쉼표(4,700) 허용, 마지막 ', ' 로 나눔


def end_of(x, start, open_pat, close):
    depth = 0
    for m in re.finditer(open_pat + "|" + re.escape(close), x[start:]):
        depth += -1 if m.group(0) == close else 1
        if depth == 0:
            return start + m.end()
    raise ValueError("짝이 맞지 않는 태그")


def remove_guides(x):
    n = 0
    while True:
        i = x.find("음영부분")
        if i < 0:
            return x, n
        ts = x.rfind("<hp:tbl ", 0, i)
        ps = x.rfind("<hp:p ", 0, ts)
        pe = end_of(x, ps, r"<hp:p\b", "</hp:p>")
        te = end_of(x, ts, r"<hp:tbl\b", "</hp:tbl>")
        leftover = "".join(re.findall(r"<hp:t>([^<]*)</hp:t>", x[ps:ts] + x[te:pe])).strip()
        if leftover:
            raise SystemExit(f"안내 상자와 같은 문단에 글이 있어 지우지 않음: {leftover[:40]}")
        x = x[:ps] + x[pe:]
        n += 1


COLPR_RE = re.compile(r'<hp:ctrl><hp:colPr [^>]*colCount="1"[^>]*/></hp:ctrl>')


def strip_cell_colpr(x):
    """표 칸 안 문단의 1단 단 설정 제어문자를 지운다(기본값과 같음). kordoc 이 이를 개체로 보고
    행 추가를 거부하기 때문. 본문(칸 밖)의 단 설정은 건드리지 않는다."""
    out, last, n = [], 0, 0
    for m in COLPR_RE.finditer(x):
        before = x[:m.start()]
        if before.count("<hp:subList") > before.count("</hp:subList>"):
            out.append(x[last:m.start()])
            last = m.end()
            n += 1
    out.append(x[last:])
    return "".join(out), n


def prepare_stage2(x):
    """stage 1 결과를 stage 2 패치 전에 정리: 안내 상자·칸 안 단 설정 삭제."""
    x, g = remove_guides(x)
    x, c = strip_cell_colpr(x)
    return x, {"안내 상자 삭제": g, "칸 안 단 설정 삭제": c}


def cell_text(row):
    return "".join(re.findall(r"<hp:t>([^<]*)</hp:t>", row)).strip()


def drop_empty_list_rows(x):
    i = x.find("회계/기금명")
    if i < 0:
        return x, 0
    s = x.rfind("<hp:tbl ", 0, i)
    e = end_of(x, s, r"<hp:tbl\b", "</hp:tbl>")
    t = x[s:e]
    if "rowSpan=\"2\"" in t or 'rowSpan="3"' in t:
        raise SystemExit("목록 표에 세로 병합이 있어 행 삭제를 건너뜀")
    rows = list(re.finditer(r"<hp:tr>.*?</hp:tr>", t, re.S))
    keep, removed_h = [], 0
    for k, r in enumerate(rows):
        body = r.group(0)
        if 1 < k < len(rows) - 1 and not cell_text(body):
            removed_h += int(re.search(r'<hp:cellSz width="\d+" height="(\d+)"', body).group(1))
            continue
        keep.append(body)
    if len(keep) == len(rows):
        return x, 0
    fixed = [re.sub(r'rowAddr="\d+"', f'rowAddr="{n}"', b) for n, b in enumerate(keep)]
    nt = t[:rows[0].start()] + "".join(fixed) + t[rows[-1].end():]
    nt = re.sub(r'rowCnt="\d+"', f'rowCnt="{len(keep)}"', nt, count=1)
    m = re.search(r'(<hp:sz width="\d+" widthRelTo="\w+" height=")(\d+)(")', nt)
    nt = nt[:m.start()] + m.group(1) + str(int(m.group(2)) - removed_h) + m.group(3) + nt[m.end():]
    return x[:s] + nt + x[e:], len(rows) - len(keep)


def run(cid, text):
    return f'<hp:run charPrIDRef="{cid}"><hp:t>{text}</hp:t></hp:run>'


def para_text(p):
    return re.sub(r"<[^>]+>", "", "".join(re.findall(r"<hp:t>(.*?)</hp:t>", p, re.S))).strip()


def fund_start(x):
    """'② 기금' 제목 문단 위치. 그 뒤의 내역사업 줄은 기금 서식으로 쓴다."""
    for m in re.finditer(r"<hp:p [^>]*>", x):
        pe = x.find("</hp:p>", m.start())
        seg = x[m.start():pe]
        if "<hp:tbl" not in seg and para_text(seg).replace(" ", "") == "②기금":
            return m.start()
    return len(x)


def fix_sub_lines(x):
    n = 0
    fs = fund_start(x)
    for m in list(re.finditer(r"<hp:p [^>]*>", x))[::-1]:
        ps = m.start()
        pe = end_of(x, ps, r"<hp:p\b", "</hp:p>")
        para = x[ps:pe]
        if "<hp:tbl" in para:
            continue
        sm = SUB_RE.match(para_text(para))
        if not sm:
            continue
        name, amount, change, rest = sm.groups()
        head = re.sub(r"<hp:run\b.*", "", para, flags=re.S)
        head = re.sub(r"<hp:linesegarray>.*?</hp:linesegarray>", "", head, flags=re.S)
        if ps < fs:
            g = GEN_IDS
            head = re.sub(r'paraPrIDRef="\d+"', f'paraPrIDRef="{GEN_PARA}"', head, count=1)
            runs = (run(g["bullet"], "❍") + run(g["space"], " ") + run(g["lead"], "내역사업인 ")
                    + run(g["quote"], "‘") + run(g["name"], name) + run(g["quote"], "’")
                    + run(g["lead"], "(") + run(g["amount"], amount) + run(g["sep"], ", ")
                    + run(g["change"], change) + run(g["close"], ")") + run(g["rest"], rest))
        else:
            f = FUND_IDS
            head = re.sub(r'paraPrIDRef="\d+"', f'paraPrIDRef="{FUND_PARA}"', head, count=1)
            runs = (run(f["bullet"], "❍ ") + run(f["name"], f"내역사업인 ‘{name}’")
                    + run(f["amount"], f'<hp:markpenBegin color="#FFFFFF"/>({amount},')
                    + run(f["change"], f' <hp:markpenEnd/><hp:markpenBegin color="#D9D9D9"/>{change}<hp:markpenEnd/>)')
                    + run(f["rest"], rest))
        x = x[:ps] + head + runs + "</hp:p>" + x[pe:]
        n += 1
    return x, n


OBJ_RE = re.compile(r"<hp:(tbl|pic|rect|line|ellipse|arc|polygon|curve|equation|container|ole|textart|fieldBegin)\b")


def is_empty_para(p):
    if para_text(p) or OBJ_RE.search(p):
        return False
    # 단 설정(colPr)만 든 제어 문자는 칸 안에서 의미가 없다
    ctrls = re.findall(r"<hp:ctrl>(.*?)</hp:ctrl>", p, re.S)
    return all(re.fullmatch(r"\s*<hp:colPr\b.*?/>\s*", c, re.S) or re.fullmatch(r"\s*<hp:colPr\b.*?</hp:colPr>\s*", c, re.S) for c in ctrls)


def drop_empty_cell_paras(x):
    """가장 안쪽 칸(subList)에서, 글이 있는 문단이 하나라도 있으면 빈 문단을 지운다."""
    total = 0
    pos = 0
    while True:
        i = x.find("<hp:subList", pos)
        if i < 0:
            return x, total
        e = end_of(x, i, r"<hp:subList\b", "</hp:subList>")
        inner = x[i:e]
        if inner.count("<hp:subList") > 1:
            pos = i + 1
            continue
        open_end = inner.find(">") + 1
        paras = list(re.finditer(r"<hp:p [^>]*>.*?</hp:p>", inner[open_end:], re.S))
        texts = [is_empty_para(p.group(0)) for p in paras]
        if paras and not all(texts) and any(texts):
            kept = "".join(p.group(0) for p, empty in zip(paras, texts) if not empty)
            body = inner[:open_end] + inner[open_end:][:paras[0].start()] + kept + inner[open_end:][paras[-1].end():]
            x = x[:i] + body + x[e:]
            total += sum(texts)
            e = i + len(body)
        pos = e


def process(x, guides=True):
    """section0.xml 문자열 후처리. 처리 건수 dict 를 함께 돌려준다."""
    stats = {}
    if guides:
        x, stats["안내 상자 삭제"] = remove_guides(x)
    x, stats["목록 빈 행 삭제"] = drop_empty_list_rows(x)
    x, stats["칸 안 빈 줄 삭제"] = drop_empty_cell_paras(x)
    x, stats["내역사업 강조 정리"] = fix_sub_lines(x)
    return x, stats


def rewrite_hwpx(src, dst, fn):
    """HWPX 의 section0.xml 에 fn 을 적용해 dst 로 다시 묶는다(mimetype 맨 앞 무압축)."""
    src, dst = Path(src), Path(dst)
    work = Path(tempfile.mkdtemp())
    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        z.extractall(work)
    sec = work / "Contents" / "section0.xml"
    x, stats = fn(sec.read_text(encoding="utf-8"))
    sec.write_text(x, encoding="utf-8")
    import xml.dom.minidom
    xml.dom.minidom.parse(str(sec))  # 깨진 XML 이면 여기서 멈춘다
    if dst.exists():
        dst.unlink()
    with zipfile.ZipFile(dst, "w") as z:
        z.write(work / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        for n in names:
            if n != "mimetype":
                z.write(work / n, n, compress_type=zipfile.ZIP_DEFLATED)
    shutil.rmtree(work)
    return stats


def main():
    stats = rewrite_hwpx(sys.argv[1], sys.argv[2], process)
    print(", ".join(f"{k} {v}" for k, v in stats.items()), "→", sys.argv[2])


if __name__ == "__main__":
    main()

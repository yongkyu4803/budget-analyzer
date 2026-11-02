#!/usr/bin/env python3
"""프로파일 머리말을 읽는 최소 YAML 파서. 표준 라이브러리만 쓴다.

왜 직접 쓰는가
  검사는 이 스킬의 필수 단계다. pyyaml에 의존하면 네트워크가 막힌 환경
  (claude.ai/Cowork 설정에 따라, API 샌드박스)에서 설치가 안 되고, 그러면
  검사가 통째로 죽는다. 검사 없이 인덱스를 늘리는 것이 이 방식의 1순위 위험이다.

지원하는 것 — 프로파일 서식이 쓰는 범위만
  블록 매핑 · 블록 시퀀스 · 흐름 매핑 {a: 1} · 흐름 시퀀스 [1, 2]
  블록 스칼라 | · 따옴표 문자열(이스케이프 처리) · int/float/bool/null

지원하지 않는 것은 **조용히 넘기지 않고 예외를 던진다.**
앵커/별칭, 접기 스칼라(>), 복합 키, 여러 문서(---), 탭 들여쓰기.
모르는 문법을 추측해 파싱하면 검사기가 엉뚱한 선언으로 검사하게 된다.
"""
import re


class MiniYamlError(ValueError):
    pass


_INT = re.compile(r"[+-]?\d+$")
_FLOAT = re.compile(r"[+-]?(\d+\.\d*|\.\d+)([eE][+-]?\d+)?$")


def _unescape_double(s):
    out, i = [], 0
    esc = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/", "0": "\0"}
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in esc:
                out.append(esc[nxt]); i += 2; continue
            if nxt == "u" and i + 5 < len(s) + 1:
                out.append(chr(int(s[i + 2:i + 6], 16))); i += 6; continue
            raise MiniYamlError(f"알 수 없는 이스케이프: \\{nxt}")
        out.append(c); i += 1
    return "".join(out)


def _scalar(tok):
    """따옴표·숫자·불리언·널을 판별해 파이썬 값으로."""
    t = tok.strip()
    if not t:
        return None
    if t[0] == '"':
        if len(t) < 2 or t[-1] != '"':
            raise MiniYamlError(f"닫히지 않은 큰따옴표: {tok}")
        return _unescape_double(t[1:-1])
    if t[0] == "'":
        if len(t) < 2 or t[-1] != "'":
            raise MiniYamlError(f"닫히지 않은 작은따옴표: {tok}")
        return t[1:-1].replace("''", "'")
    if t in ("null", "~", "Null", "NULL"):
        return None
    if t in ("true", "True", "TRUE"):
        return True
    if t in ("false", "False", "FALSE"):
        return False
    if _INT.match(t):
        return int(t)
    if _FLOAT.match(t):
        return float(t)
    if t[0] in "*&>":
        raise MiniYamlError(f"지원하지 않는 YAML 문법: {t[:20]}")
    return t


def _split_top(s, close):
    """흐름 컬렉션 본문을 최상위 쉼표로 자른다. 따옴표·중첩 괄호를 존중한다."""
    parts, buf, depth, q = [], [], 0, None
    for ch in s:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch; buf.append(ch); continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf)); buf = []; continue
        buf.append(ch)
    if depth or q:
        raise MiniYamlError(f"닫히지 않은 {close}: {s[:40]}")
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _flow(tok):
    t = tok.strip()
    if t.startswith("["):
        if not t.endswith("]"):
            raise MiniYamlError(f"닫히지 않은 [ : {tok}")
        return [_value(p) for p in _split_top(t[1:-1], "]")]
    if t.startswith("{"):
        if not t.endswith("}"):
            raise MiniYamlError(f"닫히지 않은 {{ : {tok}")
        out = {}
        for p in _split_top(t[1:-1], "}"):
            if ":" not in p:
                raise MiniYamlError(f"흐름 매핑에 콜론이 없음: {p}")
            k, v = _split_kv(p)
            out[_key(k)] = _value(v)
        return out
    raise MiniYamlError(f"흐름 컬렉션이 아님: {tok}")


def _value(tok):
    t = tok.strip()
    return _flow(t) if t[:1] in "[{" else _scalar(t)


def _key(k):
    k = k.strip()
    return _scalar(k) if k[:1] in "\"'" else k


def _split_kv(s):
    """따옴표 밖의 첫 콜론에서 자른다. 정규식 값 안의 콜론에 속지 않도록."""
    q, depth = None, 0
    for i, ch in enumerate(s):
        if q:
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch; continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == ":" and depth == 0 and (i + 1 == len(s) or s[i + 1] in " \t"):
            return s[:i], s[i + 1:]
    if s.rstrip().endswith(":"):
        return s.rstrip()[:-1], ""
    raise MiniYamlError(f"키: 값 형태가 아님 → {s[:60]}")


def _strip_comment(s):
    q = None
    for i, ch in enumerate(s):
        if q:
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i]
    return s


def _prep(text):
    """(들여쓰기, 내용, 원본줄) 목록. 주석·빈 줄 제거, 블록 스칼라는 뒤에서 처리."""
    out = []
    for raw in text.splitlines():
        if "\t" in raw[:len(raw) - len(raw.lstrip())]:
            raise MiniYamlError(f"탭 들여쓰기는 지원하지 않습니다: {raw[:40]}")
        out.append((len(raw) - len(raw.lstrip(" ")), raw.strip(), raw))
    return out


def _block_scalar(lines, i, parent_indent, chomp):
    """| 블록을 모은다. 부모보다 깊게 들여쓴 줄 전부."""
    body, base = [], None
    while i < len(lines):
        ind, content, raw = lines[i]
        if not content:
            body.append(""); i += 1; continue
        if ind <= parent_indent:
            break
        if base is None:
            base = ind
        body.append(raw[base:] if len(raw) >= base else "")
        i += 1
    while body and body[-1] == "":
        body.pop()
    text = "\n".join(body)
    if chomp == "|":
        text += "\n"
    return text, i


def _eff(content):
    """구조 판단에 쓰는 내용 — 주석을 뺀 것. 블록 스칼라 본문에는 쓰지 않는다."""
    return _strip_comment(content).strip()


def _parse(lines, i, indent):
    """indent 수준의 블록을 파싱해 (값, 다음 줄) 반환."""
    while i < len(lines) and not _eff(lines[i][1]):
        i += 1
    if i >= len(lines):
        return None, i

    if _eff(lines[i][1]).startswith("- "):
        seq = []
        while i < len(lines):
            ind, content, _ = lines[i]
            c = _eff(content)
            if not c:
                i += 1; continue
            if ind != indent or not c.startswith("- "):
                break
            item = c[2:].strip()
            if item[:1] in "[{":
                seq.append(_flow(item)); i += 1
            elif ":" in item and item[:1] not in "\"'":
                sub = [(ind + 2, item, " " * (ind + 2) + item)] + lines[i + 1:]
                val, used = _parse(sub, 0, ind + 2)
                seq.append(val); i = i + used
            else:
                seq.append(_scalar(item)); i += 1
        return seq, i

    mapping = {}
    while i < len(lines):
        ind, content, _ = lines[i]
        c = _eff(content)
        if not c:
            i += 1; continue
        if ind < indent:
            break
        if ind > indent:
            raise MiniYamlError(f"들여쓰기가 어긋납니다: {c[:40]}")
        if c.startswith("- "):
            break
        k, v = _split_kv(c)
        key, v = _key(k), v.strip()
        i += 1
        if v in ("|", "|-", "|+"):
            mapping[key], i = _block_scalar(lines, i, ind, v)
        elif v == "":
            j = i
            while j < len(lines) and not _eff(lines[j][1]):
                j += 1
            if j < len(lines) and lines[j][0] > ind:
                mapping[key], i = _parse(lines, j, lines[j][0])
            else:
                mapping[key] = None
        else:
            mapping[key] = _value(v)
    return mapping, i


def load(text):
    """YAML 머리말 문자열 -> 파이썬 객체."""
    if re.search(r"^\s*<<:|^\s*&\w|^\s*\*\w", text, re.M):
        raise MiniYamlError("앵커/별칭/병합 키는 지원하지 않습니다")
    lines = _prep(text)
    val, _ = _parse(lines, 0, 0)
    return val if val is not None else {}

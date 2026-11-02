#!/usr/bin/env python3
"""서면질의 입력 JSON → 완성 HWPX 한 번에 만들기.

사용: python3 build.py spec.json 출력.hwpx [--template 견본.hwpx] [--keep-work]

순서
 1. stage 1 마크다운으로 kordoc patch (감액 표는 첫 행만, 칸 안 안내 상자 유지)
 2. 안내 상자·칸 안 단 설정(colPr) 삭제 — 행 추가를 막는 개체 제거
 3. stage 2 마크다운으로 kordoc patch (모든 행)
 4. 후처리(목록 빈 행·칸 안 빈 줄 삭제, 내역사업 강조 서식) 후 다시 묶기
 5. kordoc validate + check.py

kordoc 찾는 순서: 환경변수 KORDOC_CMD(예: "node /path/cli.js") → ~/.claude/skills/kordoc/engine/env.json
→ PATH 의 kordoc → npx -y kordoc
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_markdown  # noqa: E402
import postprocess  # noqa: E402


def kordoc_cmd():
    if os.environ.get("KORDOC_CMD"):
        return shlex.split(os.environ["KORDOC_CMD"])
    env = Path.home() / ".claude/skills/kordoc/engine/env.json"
    if env.exists():
        e = json.loads(env.read_text())
        return [e["node"], e["kordoc_cli"]]
    if shutil.which("kordoc"):
        return ["kordoc"]
    if shutil.which("npx"):
        return ["npx", "-y", "kordoc"]
    sys.exit("kordoc 을 찾지 못함 — KORDOC_CMD 를 지정하거나 kordoc 을 설치하세요")


def patch(k, original, md_text, out, work):
    md = work / (out.stem + ".md")
    md.write_text(md_text, encoding="utf-8")
    r = subprocess.run(k + ["patch", str(original), str(md), "-o", str(out), "--json", "--silent"],
                       capture_output=True, text=True, env={**os.environ, "KORDOC_OFFLINE": "1"})
    if r.returncode not in (0, 2) or not out.exists():
        sys.exit(f"kordoc patch 실패 ({original.name}):\n{r.stderr or r.stdout}")
    res = json.loads(r.stdout)
    hard = [s for s in res.get("skipped", []) if not s.get("partial")]
    if hard:
        msg = "\n".join(f"- {s['reason']}: {s.get('before', '')[:60]}" for s in hard)
        sys.exit(f"반영되지 않은 편집이 있음 ({out.name}):\n{msg}")
    return res


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    spec_path, out = Path(args[0]), Path(args[1]).resolve()
    tmpl = Path(args[args.index("--template") + 1]) if "--template" in args else HERE.parent / "assets/template_2027.hwpx"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    k = kordoc_cmd()
    work = Path(tempfile.mkdtemp(prefix="bwq-"))

    s1 = work / "stage1.hwpx"
    patch(k, tmpl, make_markdown.build(spec, stage=1), s1, work)
    s1b = work / "stage1_noguide.hwpx"
    postprocess.rewrite_hwpx(s1, s1b, postprocess.prepare_stage2)
    s2 = work / "stage2.hwpx"
    res = patch(k, s1b, make_markdown.build(spec, stage=2), s2, work)
    stats = postprocess.rewrite_hwpx(s2, out, lambda x: postprocess.process(x, guides=False))

    v = subprocess.run(k + ["validate", str(out)], capture_output=True, text=True, env={**os.environ, "KORDOC_OFFLINE": "1"})
    c = subprocess.run([sys.executable, str(HERE / "check.py"), str(out), str(tmpl)], capture_output=True, text=True)
    print(f"패치 적용 {res.get('applied')}건 / " + ", ".join(f"{a} {b}" for a, b in stats.items()))
    print((v.stdout + v.stderr).strip().splitlines()[-1] if (v.stdout + v.stderr).strip() else "validate 출력 없음")
    print(c.stdout.strip())
    if "--keep-work" in args:
        print(f"중간 파일: {work}")
    else:
        shutil.rmtree(work)
    if v.returncode != 0 or c.returncode != 0:
        sys.exit(1)
    print(f"완성: {out}")


if __name__ == "__main__":
    main()

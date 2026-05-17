from pathlib import Path
import fitz


def main():
    p = Path("uploads")
    if not p.exists():
        print("No uploads folder")
        return

    for f in sorted(p.iterdir()):
        print("---", f.name)
        if f.suffix.lower() == ".txt":
            txt = f.read_text(encoding="utf-8", errors="ignore")
            print(txt.strip()[:1000])
        elif f.suffix.lower() == ".pdf":
            try:
                doc = fitz.open(f)
                if len(doc) >= 1:
                    text = doc[0].get_text()
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    for ln in lines[:40]:
                        print(ln)
                else:
                    print("(empty pdf)")
                doc.close()
            except Exception as e:
                print("error reading pdf", e)
        else:
            print("unknown file type")


if __name__ == "__main__":
    main()

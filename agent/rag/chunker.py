import json
import re
from pathlib import Path


def chunk_markdown(file_path: str | Path) -> list[dict]:
    """把 Markdown 文档切成适合检索的片段。"""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")

    if path.stem == "FAQ":
        sections = _chunk_faq(content)
    else:
        sections = _chunk_by_h2(content)

    chunks = []
    for title, text in sections:
        if not text:
            continue

        chunks.append(
            {
                "doc": path.stem,
                "section": title,
                "text": text,
            }
        )

    for index, chunk in enumerate(chunks, start=1):
        chunk["chunk_id"] = f"{path.stem}-{index:02d}"

    return chunks


def _chunk_by_h2(content: str) -> list[tuple[str, str]]:
    """普通政策文档按二级标题切分。"""
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)
    chunks = []

    for section in sections:
        lines = section.strip().splitlines()
        if not lines or not lines[0].startswith("## "):
            continue

        title = lines[0][3:].strip()
        text = "\n".join(lines[1:]).strip()
        chunks.append((title, text))

    return chunks


def _chunk_faq(content: str) -> list[tuple[str, str]]:
    """FAQ 按每个问题切分，并保留所属分类。"""
    parent_title = ""
    current_title = ""
    current_lines: list[str] = []
    chunks = []

    def save_current() -> None:
        if not current_title:
            return

        section = f"{parent_title} / {current_title}" if parent_title else current_title
        chunks.append((section, "\n".join(current_lines).strip()))

    for line in content.splitlines():
        if line.startswith("## "):
            save_current()
            current_title = ""
            current_lines = []
            parent_title = line[3:].strip()
        elif re.match(r"^### Q\d+\.\d+", line):
            save_current()
            current_title = line[4:].strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)

    save_current()
    return chunks


def chunk_markdown_dir(dir_path: str | Path) -> list[dict]:
    """扫描目录下所有 Markdown 文档并合并切片。"""
    all_chunks = []
    for path in sorted(Path(dir_path).glob("*.md")):
        all_chunks.extend(chunk_markdown(path))
    return all_chunks


def save_chunks(chunks: list[dict], file_path: str | Path) -> None:
    """把切片保存成 JSON 文件。"""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    chunks = chunk_markdown_dir("knowledge")
    save_chunks(chunks, "data/chunks.json")
    print(f"共生成 {len(chunks)} 个切片")

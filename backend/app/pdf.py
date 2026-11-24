"""Minimal dependency-free PDF writer for invoices and receipts.

Text is escaped and restricted to Latin-1/ASCII so generated documents cannot
embed active content. This is intentionally a text-only PDF, not a template
engine; all values come from persisted database records.
"""


def _escape(text: str) -> str:
    cleaned = "".join(character if 32 <= ord(character) < 127 else "?" for character in str(text))
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def simple_pdf(title: str, lines: list[str], output_path: str | None = None) -> bytes:
    content_lines = [f"BT /F1 16 Tf 48 792 Td 20 TL ({_escape(title)}) Tj T* /F1 11 Tf"]
    content_lines.extend(f"({_escape(line)}) Tj T*" for line in lines)
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("ascii")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{index} 0 obj\n".encode("ascii"))
        document.extend(body)
        document.extend(b"\nendobj\n")

    xref_position = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    document.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF\n".encode("ascii")
    )

    result = bytes(document)
    if output_path:
        with open(output_path, "wb") as handle:
            handle.write(result)
    return result

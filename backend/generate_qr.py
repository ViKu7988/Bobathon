#!/usr/bin/env python3
"""
generate_qr.py — generates a QR code PNG and an HTML page with
the QR code embedded, given a URL.
Usage:  python generate_qr.py <url> [output_path]
EcoComply | IBM Bobathon 2025
"""

import sys
import os
import io
import base64
import qrcode
from qrcode.image.styledpil import StyledPilImage

def make_qr_b64(url: str) -> str:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
                       box_size=10, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a56db", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def write_qr_page(url: str, out_html: str, out_png: str):
    b64 = make_qr_b64(url)

    # Save PNG
    import qrcode as qc
    qr = qc.QRCode(error_correction=qc.constants.ERROR_CORRECT_H, box_size=12, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a56db", back_color="white")
    img.save(out_png)
    print(f"QR PNG → {out_png}")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>🛡️ Regulatory Radar — Live Demo QR</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:-apple-system,"Segoe UI",sans-serif;background:#f0f4ff;
          display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px;}}
    .card{{background:#fff;border-radius:16px;padding:40px 32px;text-align:center;
           max-width:420px;width:100%;box-shadow:0 8px 32px rgba(26,86,219,.15);}}
    .logo{{font-size:48px;margin-bottom:12px;}}
    h1{{font-size:22px;font-weight:800;color:#1a56db;margin-bottom:4px;}}
    .sub{{font-size:14px;color:#57606a;margin-bottom:28px;line-height:1.5;}}
    .qr-wrap{{background:#f7f8fa;border-radius:12px;padding:20px;display:inline-block;margin-bottom:24px;}}
    .qr-wrap img{{width:220px;height:220px;display:block;}}
    .url-box{{background:#f0f4ff;border-radius:8px;padding:10px 14px;
              font-size:12px;color:#1a56db;word-break:break-all;margin-bottom:20px;
              font-family:monospace;}}
    .steps{{text-align:left;font-size:13px;color:#57606a;line-height:1.8;}}
    .steps strong{{color:#1f2328;}}
    .divider{{border:none;border-top:1px solid #e5e7eb;margin:20px 0;}}
    .powered{{font-size:11px;color:#57606a;margin-top:16px;}}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">🛡️</div>
    <h1>Regulatory Radar</h1>
    <p class="sub">Live Demo — IBM Bobathon 2025 · EcoComply<br>
    Scan to open on your phone</p>

    <div class="qr-wrap">
      <img src="data:image/png;base64,{b64}" alt="QR Code"/>
    </div>

    <div class="url-box">{url}</div>

    <div class="steps">
      <strong>1.</strong> Scan the QR code with your phone camera<br>
      <strong>2.</strong> Fill in your company profile (60 seconds)<br>
      <strong>3.</strong> Select your product categories<br>
      <strong>4.</strong> Enter your phone number<br>
      <strong>5.</strong> Hit <strong>"Activate My Radar"</strong><br>
      <strong>6.</strong> Watch your phone buzz ✅
    </div>

    <hr class="divider"/>
    <p class="powered">
      Powered by <strong>IBM Bob (Watsonx)</strong> &amp; <strong>Twilio</strong>
    </p>
  </div>
</body>
</html>"""

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"QR HTML → {out_html}")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8888/onboard.html"
    base = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(base, exist_ok=True)
    write_qr_page(url,
                  out_html=os.path.join(base, "demo_qr.html"),
                  out_png=os.path.join(base, "demo_qr.png"))
    print(f"\nURL encoded: {url}")
    print("Done ✅")

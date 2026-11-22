#!/usr/bin/env python3
"""End-to-end check of a deployed CloudVault stack.

Creates a throwaway Cognito user, then does what a person does through the API:
upload a text file, a PNG and a PDF, wait for the AI summaries, chat, ask across the
library, generate study material, favourite, move, share, open the share link,
download and delete. Browser headers (Origin) are sent so CORS is checked too.
The user and every file it created are removed at the end.

Needs the AWS CLI signed in with the deploy role, and AWS_REGION set.
Standard library only. Exits 1 if any check fails.
"""
import json
import os
import re
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

PROJECT = os.environ.get("PROJECT", "cloudvault-poc")
REGION = os.environ["AWS_REGION"]
FOLDER = "Smoke test"
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name, (" - " + detail) if detail else ""), flush=True)
    return ok


def aws(*args):
    proc = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("aws %s failed: %s" % (" ".join(args[:2]), proc.stderr.strip()[:300]))
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def http(method, url, headers=None, body=None, timeout=60):
    """(status, headers, body bytes). Never raises on an HTTP error status."""
    headers = dict(headers or {})
    data = body
    if body is not None and not isinstance(body, bytes):
        data = json.dumps(body).encode()
        headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as error:
        return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()
    except Exception as error:  # network-level failure
        return 0, {}, str(error).encode()


def jsonify(raw):
    try:
        return json.loads(raw)
    except Exception:
        return {}


# ---- sample files -----------------------------------------------------------

def make_png(width=320, height=240):
    rows = []
    for y in range(height):
        row = bytearray(b"\x00")
        for x in range(width):
            if 60 <= x < 260 and 50 <= y < 190:
                row += bytes((200, 40, 40))      # a red rectangle
            elif y > 200:
                row += bytes((60, 140, 60))      # a green strip
            else:
                row += bytes((250, 250, 250))
        rows.append(bytes(row))

    def chunk(kind, payload):
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def make_pdf(lines):
    text = " 0 -24 Td ".join("(%s) Tj" % line for line in lines)
    stream = ("BT /F1 16 Tf 72 700 Td %s ET" % text).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return out


TEXT_BODY = (b"Quarterly report. Revenue grew 12 percent on the previous quarter, driven by the new "
             b"subscription tier. Churn fell to 3.1 percent. Support costs stayed flat. "
             b"Two engineers will be hired in the fourth quarter.\n")
FILES = [
    ("quarterly notes.txt", TEXT_BODY),
    ("red box.png", make_png()),
    ("board summary.pdf", make_pdf([
        "Board summary: product launch review",
        "The launch met its adoption target in March.",
        "Customer satisfaction rose to 92 percent.",
        "The next milestone is expansion into two new regions.",
    ])),
]


# ---- discover the stack ----------------------------------------------------

def discover():
    distributions = aws("cloudfront", "list-distributions").get("DistributionList", {}).get("Items", [])
    site_domain = next(d["DomainName"] for d in distributions if d.get("Comment") == "%s frontend" % PROJECT)
    site = "https://" + site_domain
    status, _, body = http("GET", site + "/config.js")
    config = body.decode("utf-8", "replace")
    api = re.search(r'apiBase:\s*"([^"]+)"', config).group(1)
    client = re.search(r'cognitoClientId:\s*"([^"]+)"', config).group(1)
    pools = aws("cognito-idp", "list-user-pools", "--max-results", "60")["UserPools"]
    pool = next(p["Id"] for p in pools if p["Name"] == "%s-users" % PROJECT)
    return site, api, client, pool


def main():
    site, api, client, pool = discover()
    print("site:", site)
    print("api: ", api)

    email = "smoke-%d@example.com" % int(time.time())
    password = "Smoke-Test-%d-Aa" % int(time.time())
    created_docs = []
    token = None
    try:
        aws("cognito-idp", "admin-create-user", "--user-pool-id", pool, "--username", email,
            "--message-action", "SUPPRESS", "--user-attributes",
            "Name=email,Value=" + email, "Name=email_verified,Value=true")
        aws("cognito-idp", "admin-set-user-password", "--user-pool-id", pool, "--username", email,
            "--password", password, "--permanent")
        auth = aws("cognito-idp", "initiate-auth", "--auth-flow", "USER_PASSWORD_AUTH", "--client-id", client,
                   "--auth-parameters", "USERNAME=%s,PASSWORD=%s" % (email, password))
        token = auth["AuthenticationResult"]["IdToken"]
        print("::add-mask::" + token, flush=True)
        check("sign in with a Cognito user (the page's own sign-in flow)", True)

        def call(method, path, body=None, auth_header=True, extra=None):
            headers = {"Origin": site}
            if auth_header:
                headers["Authorization"] = "Bearer " + token
            headers.update(extra or {})
            status, response_headers, raw = http(method, api + path, headers, body)
            return status, response_headers, jsonify(raw)

        # ---- site and API basics
        status, _, body = http("GET", site + "/")
        check("site serves the app", status == 200 and b"CloudVault AI" in body, "HTTP %s" % status)
        status, _, body = http("GET", site + "/share.html")
        check("site serves the share page", status == 200, "HTTP %s" % status)
        status, _, _ = call("GET", "/documents", auth_header=False)
        check("API refuses a request with no token", status == 401, "HTTP %s" % status)
        status, headers, _ = call("GET", "/documents")
        check("API accepts the token and allows the site origin (CORS)",
              status == 200 and headers.get("access-control-allow-origin") == site,
              "HTTP %s, allow-origin=%s" % (status, headers.get("access-control-allow-origin")))

        # ---- folders
        status, _, _ = call("POST", "/create-folder", {"name": FOLDER})
        check("create a folder", status == 200, "HTTP %s" % status)
        status, _, data = call("GET", "/folders")
        check("list folders", status == 200 and FOLDER in data.get("folders", []), "HTTP %s" % status)

        # ---- uploads, exactly as the browser does them
        for filename, content in FILES:
            query = "/upload-url?filename=" + urllib.parse.quote(filename)
            status, _, data = call("GET", query)
            url = data.get("uploadUrl", "")
            host = urllib.parse.urlparse(url).netloc
            check("upload URL for '%s' uses the regional S3 address and V4 signing" % filename,
                  status == 200 and host.endswith(".s3.%s.amazonaws.com" % REGION) and "X-Amz-Signature" in url,
                  host or "HTTP %s" % status)
            if not url:
                continue
            status, headers, raw = http("OPTIONS", url, {
                "Origin": site, "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "content-type"})
            check("S3 allows the browser's preflight for '%s'" % filename,
                  status == 200 and headers.get("access-control-allow-origin") in (site, "*"),
                  "HTTP %s, allow-origin=%s" % (status, headers.get("access-control-allow-origin")))
            status, headers, raw = http("PUT", url, {"Content-Type": "application/octet-stream", "Origin": site}, content)
            check("upload '%s' to S3" % filename,
                  status == 200 and headers.get("access-control-allow-origin") in (site, "*"),
                  "HTTP %s %s" % (status, raw[:120].decode("utf-8", "replace") if status != 200 else ""))

        # ---- the AI processing that follows an upload
        wanted = {name for name, _ in FILES}
        documents = {}
        deadline = time.time() + 180
        while time.time() < deadline:
            status, _, data = call("GET", "/documents")
            documents = {d["filename"]: d for d in data if isinstance(d, dict)} if status == 200 else {}
            if all(documents.get(n, {}).get("status") == "summarized" for n in wanted):
                break
            time.sleep(6)
        for filename, _ in FILES:
            doc = documents.get(filename)
            if doc:
                created_docs.append(doc["document_id"])
            check("'%s' appears in the library with an AI summary" % filename,
                  bool(doc) and doc.get("status") == "summarized" and bool(doc.get("summary")),
                  ("status=%s" % doc.get("status")) if doc else "not in the library after 180s")
        text_doc = documents.get("quarterly notes.txt")
        if text_doc and text_doc.get("summary"):
            print("    summary preview:", text_doc["summary"][:110].replace("\n", " "))

        if text_doc:
            doc_id = text_doc["document_id"]

            status, _, data = call("POST", "/chat", {"document_id": doc_id, "question": "How much did revenue grow?", "history": []})
            check("chat with a document", status == 200 and bool(data.get("answer")),
                  (data.get("answer") or str(data))[:100].replace("\n", " "))

            status, _, data = call("POST", "/ask-assistant", {"question": "Which files are in my library?", "history": []})
            check("ask across the whole library", status == 200 and bool(data.get("answer")),
                  (data.get("answer") or str(data))[:100].replace("\n", " "))

            ok, detail = False, ""
            for _ in range(3):  # the model occasionally returns malformed JSON; the app asks the user to retry
                status, _, data = call("POST", "/generate-study-material", {"document_id": doc_id})
                ok = status == 200 and bool(data.get("mcqs")) and bool(data.get("flashcards"))
                detail = "%d questions, %d flashcards" % (len(data.get("mcqs", [])), len(data.get("flashcards", []))) if ok else str(data)[:120]
                if ok:
                    break
            check("generate study material", ok, detail)

            status, _, _ = call("PATCH", "/update-document", {"document_id": doc_id, "favorite": True, "folder": FOLDER})
            status2, _, data = call("GET", "/documents")
            moved = next((d for d in data if d.get("document_id") == doc_id), {}) if status2 == 200 else {}
            check("favourite and move a document", status == 200 and moved.get("favorite") is True and moved.get("folder") == FOLDER,
                  "HTTP %s" % status)

            status, _, data = call("GET", "/download-url?document_id=" + doc_id)
            url = data.get("downloadUrl", "")
            fetched_status, _, fetched = http("GET", url) if url else (0, {}, b"")
            check("download a file with a pre-signed link", status == 200 and fetched_status == 200 and fetched == TEXT_BODY,
                  "HTTP %s then %s" % (status, fetched_status))

            status, _, data = call("POST", "/create-share", {"document_id": doc_id, "expiry_hours": 1})
            share_url = data.get("shareUrl", "")
            check("create a share link on the site's address", status == 200 and share_url.startswith(site + "/share.html?id="),
                  share_url[:80] or "HTTP %s" % status)
            share_id = urllib.parse.parse_qs(urllib.parse.urlparse(share_url).query).get("id", [""])[0]
            status, _, data = call("GET", "/shared-file?share_id=" + share_id, auth_header=False)
            shared_url = data.get("downloadUrl", "")
            shared_status, _, shared_body = http("GET", shared_url) if shared_url else (0, {}, b"")
            check("open the share link with no account", status == 200 and shared_status == 200 and shared_body == TEXT_BODY,
                  "HTTP %s then %s" % (status, shared_status))
            status, _, _ = call("GET", "/shared-file?share_id=does-not-exist", auth_header=False)
            check("an invalid share link is refused", status == 404, "HTTP %s" % status)

        # ---- cleanup through the app's own endpoints
        for doc_id in created_docs:
            call("DELETE", "/delete-document?document_id=" + doc_id)
        status, _, data = call("GET", "/documents")
        check("delete documents", status == 200 and not [d for d in data if d.get("document_id") in created_docs],
              "%d left" % len([d for d in data if d.get("document_id") in created_docs]) if status == 200 else "HTTP %s" % status)
        status, _, _ = call("DELETE", "/delete-folder?name=" + urllib.parse.quote(FOLDER))
        check("delete a folder", status == 200, "HTTP %s" % status)
    finally:
        try:
            aws("cognito-idp", "admin-delete-user", "--user-pool-id", pool, "--username", email)
            print("removed the test user")
        except Exception as error:
            print("could not remove the test user %s: %s" % (email, error))

    failed = [name for name, ok in results if not ok]
    print("\n%d checks, %d passed, %d failed" % (len(results), len(results) - len(failed), len(failed)))
    for name in failed:
        print("  FAILED:", name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

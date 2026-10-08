"""Session for the Sales tenant (separate cookie jar)."""
import sys, os, http.cookiejar, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("UA_IDP_ID", "66802ae3aacb5f24ffb824b3") if not os.environ.get("UA_IDP_ID") else None
import ua
ua.JAR_PATH = ua.JAR_PATH + "_sales"
ua.jar = http.cookiejar.LWPCookieJar(ua.JAR_PATH)
if os.path.exists(ua.JAR_PATH): ua.jar.load(ignore_discard=True, ignore_expires=True)
ua.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(ua.jar))

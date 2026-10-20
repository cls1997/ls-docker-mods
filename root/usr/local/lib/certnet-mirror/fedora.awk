# Modify only the main release/update sections; keep keys, signatures, third-
# party repos and disabled debug/source sections exactly as supplied by Fedora.
function finish() {
    if (section == "fedora")
        print "mirrorlist=https://mirrors.cernet.edu.cn/api/rpm/mirrorlist/fedora/releases/$releasever/Everything/$basearch/os/"
    if (section == "updates")
        print "mirrorlist=https://mirrors.cernet.edu.cn/api/rpm/mirrorlist/fedora/updates/$releasever/Everything/$basearch/"
}
/^[[:space:]]*\[/ {
    finish()
    section = $0
    sub(/^[[:space:]]*\[/, "", section)
    sub(/\].*$/, "", section)
}
(section == "fedora" || section == "updates") && /^[[:space:]]*(baseurl|metalink|mirrorlist)[[:space:]]*=/ { next }
{ print }
END { finish() }

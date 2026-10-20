# Rewrites only recognised distribution URLs, preserving options, keyrings,
# components, enabled/disabled state and third-party repositories.
function url(value, security,    name, plain) {
    plain = value
    sub(/\/$/, "", plain)
    if (distro == "ubuntu" && plain ~ /^https?:\/\/(([a-z][a-z]\.)?archive\.ubuntu\.com\/ubuntu|security\.ubuntu\.com\/ubuntu|ports\.ubuntu\.com\/ubuntu-ports)$/) {
        name = (arch ~ /^(x86_64|amd64|i[3-6]86)$/) ? "ubuntu" : "ubuntu-ports"
    } else if (distro == "debian" && plain ~ /^https?:\/\/((deb|httpredir|ftp)\.debian\.org\/debian)$/) {
        name = "debian"
    } else if (distro == "debian" && plain ~ /^https?:\/\/(security\.debian\.org(\/debian-security|\/debian)?|deb\.debian\.org\/debian-security)$/) {
        name = "debian-security"
        security = 1
    } else if (distro == "kali" && plain ~ /^https?:\/\/(http\.kali\.org|kali\.download)\/kali$/) {
        return "https://mirrors.cernet.edu.cn/kali"
    } else {
        return value
    }
    # The official-index option keeps timely security metadata and mirror fallback.
    return "mirror+https://mirrors.cernet.edu.cn/api/apt/mirrorlist/" name (security ? "?official_index=1" : "")
}

function rewrite_line(line, security,    result, token) {
    result = ""
    while (match(line, /[^[:space:]]+/)) {
        result = result substr(line, 1, RSTART - 1)
        token = substr(line, RSTART, RLENGTH)
        result = result url(token, security)
        line = substr(line, RSTART + RLENGTH)
    }
    return result line
}

# Emit a DEB822 stanza, optionally splitting mixed normal/security Suites while
# retaining every other field, including folded URIs and inline Signed-By keys.
function emit(lines, count, suites, security,    i, field, continuation, line) {
    continuation = ""
    for (i = 1; i <= count; i++) {
        line = lines[i]
        if (line ~ /^[A-Za-z][A-Za-z-]*:/) {
            field = tolower(line)
            sub(/:.*/, "", field)
            continuation = field
        } else if (line !~ /^[ \t]/) {
            continuation = ""
        }
        if (continuation == "uris") {
            print rewrite_line(line, security)
        } else if (continuation == "suites" && suites != "") {
            if (line ~ /^[Ss][Uu][Ii][Tt][Ee][Ss]:/) print "Suites: " suites
        } else {
            print line
        }
    }
}

function stanza(    lines, count, i, field, suites, text, tokens, n, normal, security, j, known) {
    count = split($0, lines, "\n")
    suites = ""
    field = ""
    known = 0
    for (i = 1; i <= count; i++) {
        if (lines[i] ~ /^[A-Za-z][A-Za-z-]*:/) {
            field = tolower(lines[i]); sub(/:.*/, "", field)
        } else if (lines[i] !~ /^[ \t]/) field = ""
        if (field == "suites") {
            text = lines[i]; sub(/^[^:]+:/, "", text)
            suites = suites " " text
        }
        if (field == "uris" && rewrite_line(lines[i], 0) != lines[i]) known = 1
    }
    if (!known) { print $0; return }
    n = split(suites, tokens, /[[:space:]]+/)
    normal = security = ""
    for (j = 1; j <= n; j++) {
        if (tokens[j] == "") continue
        if (tokens[j] ~ /(-security|\/updates)$/) security = security (security ? " " : "") tokens[j]
        else normal = normal (normal ? " " : "") tokens[j]
    }
    if (normal != "") emit(lines, count, normal, 0)
    if (normal != "" && security != "") print ""
    if (security != "") emit(lines, count, security, 1)
    if (normal == "" && security == "") emit(lines, count, "", 0)
}

BEGIN { if (deb822 == "sources") { RS = ""; ORS = "\n" } }
deb822 == "sources" { if (NR > 1) print ""; stanza(); next }
/^[[:space:]]*deb(-src)?[[:space:]]/ {
    # Security suite recognition also works with a [signed-by=... arch=...] block.
    print rewrite_line($0, $0 ~ /[[:space:]][^[:space:]]+(-security|\/updates)[[:space:]]/)
    next
}
{ print }

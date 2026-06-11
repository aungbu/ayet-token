cat > /tmp/wst_i18n.py <<'PYEOF'
import sys
F = sys.argv[1] if len(sys.argv) > 1 else "/var/www/wst.aucfans.com/index.html"
s = open(F, encoding="utf-8").read()

def bi(en, ja):
    return '<span class="i18-en">%s</span><span class="i18-ja">%s</span>' % (en, ja)

# ---------- 1) i18n CSS (idempotent) ----------
if '.i18-en' not in s:
    css = (".i18-ja{display:none}\n"
           "body.lang-ja .i18-en{display:none}body.lang-ja .i18-ja{display:inline}\n"
           "body.lang-en .i18-ja{display:none}body.lang-en .i18-en{display:inline}\n"
           ".lang-tog{display:inline-flex;gap:2px;background:var(--paper-2);border:1px solid var(--line);border-radius:9px;padding:2px;margin-left:16px}\n"
           ".lang-btn{border:none;background:transparent;color:var(--slate);font-family:var(--display);font-size:12px;font-weight:600;padding:5px 11px;border-radius:7px;cursor:pointer}\n"
           ".lang-btn.active{background:var(--ink);color:#fff}\n"
           "@media(max-width:760px){.lang-tog{margin-left:8px}}\n")
    anchor = '.wrap{max-width:1180px;margin:0 auto;padding:0 28px}'
    assert anchor in s, "css anchor"
    s = s.replace(anchor, css + anchor, 1)

# ---------- 2) body default language = Japanese ----------
if '<body class="lang-ja">' not in s:
    assert '<body>' in s, "body tag"
    s = s.replace('<body>', '<body class="lang-ja">', 1)

# ---------- 3) language toggle button in nav (idempotent) ----------
if 'class="lang-tog"' not in s:
    navanchor = '    </div>\n  </div>\n</nav>'
    assert navanchor in s, "nav anchor"
    s = s.replace(navanchor,
        '    </div>\n    <div class="lang-tog"><button class="lang-btn active" data-lang="ja">日本語</button><button class="lang-btn" data-lang="en">EN</button></div>\n  </div>\n</nav>', 1)

# ---------- 4) toggle JS (idempotent) ----------
if 'language toggle' not in s:
    js_anchor = '<script>\n// copy buttons'
    assert js_anchor in s, "js anchor"
    s = s.replace(js_anchor,
        "<script>\n// language toggle\n"
        "document.querySelectorAll('.lang-btn').forEach(b=>b.addEventListener('click',()=>{"
        "var l=b.getAttribute('data-lang');document.body.classList.remove('lang-ja','lang-en');"
        "document.body.classList.add('lang-'+l);"
        "document.querySelectorAll('.lang-btn').forEach(x=>x.classList.toggle('active',x===b));}));\n\n"
        "// copy buttons", 1)

# ---------- 5) translation pairs ----------
P = []
# NAV (Architecture / Why L1 / Q&A appear in nav AND footer -> replace all)
P += [
 ('<a href="#layers">Architecture</a>', '<a href="#layers">%s</a>' % bi('Architecture','アーキテクチャ')),
 ('<a href="#token">Token</a>', '<a href="#token">%s</a>' % bi('Token','トークン')),
 ('<a href="#usecases">Use Cases</a>', '<a href="#usecases">%s</a>' % bi('Use Cases','ユースケース')),
 ('<a href="#why">Why L1</a>', '<a href="#why">%s</a>' % bi('Why L1','なぜL1か')),
 ('<a href="#qa">Q&amp;A</a>', '<a href="#qa">%s</a>' % bi('Q&amp;A','Q&amp;A')),
 ('<a href="#contact" class="nav-cta">Contact</a>', '<a href="#contact" class="nav-cta">%s</a>' % bi('Contact','お問い合わせ')),
]
# HERO
P += [
 ('<span class="dot"></span>FME L1 · Enterprise Logistics Proof Layer',
  '<span class="dot"></span>' + bi('FME L1 · Enterprise Logistics Proof Layer','FME L1 · エンタープライズ物流証明レイヤー')),
 ('<h1>The proof layer for <span class="em">physical logistics</span>.</h1>',
  '<h1>' + bi('The proof layer for <span class="em">physical logistics</span>.','物流のための<span class="em">証明レイヤー</span>。') + '</h1>'),
 ('<p class="lede"><strong>World Supply Token (WST)</strong> turns every pickup, hub scan, and delivery into a signed, tamper-evident event on FME Layer 1 — so a shipment isn\'t just tracked, it\'s <strong>proven</strong>.</p>',
  '<p class="lede">' + bi('<strong>World Supply Token (WST)</strong> turns every pickup, hub scan, and delivery into a signed, tamper-evident event on FME Layer 1 — so a shipment isn\'t just tracked, it\'s <strong>proven</strong>.','<strong>World Supply Token（WST）</strong>は、集荷・拠点スキャン・配達のすべてを、FME Layer 1上の署名済みで改ざん検知可能なイベントに変えます。荷物は単に追跡されるのではなく、<strong>証明</strong>されます。') + '</p>'),
 ('Built for Sagawa Holdings logistics. Compatible with Aura DPP and Avery Dennison RFID/NFC/QR. Positioned as enterprise infrastructure — not a speculative cryptocurrency.',
  bi('Built for Sagawa Holdings logistics. Compatible with Aura DPP and Avery Dennison RFID/NFC/QR. Positioned as enterprise infrastructure — not a speculative cryptocurrency.','佐川グローバルロジスティクス向けに設計。Aura DPPおよびAvery Dennison RFID/NFC/QRと互換。投機的な暗号資産ではなく、エンタープライズ・インフラとして位置づけられます。')),
 ('class="btn btn-primary">See live PoC use cases',
  'class="btn btn-primary">' + bi('See live PoC use cases','実証ユースケースを見る')),
 ('<a href="#token" class="btn btn-ghost">Token details</a>',
  '<a href="#token" class="btn btn-ghost">' + bi('Token details','トークン詳細') + '</a>'),
 ('<div class="trust-label">Designed to interoperate with</div>',
  '<div class="trust-label">' + bi('Designed to interoperate with','相互運用を想定') + '</div>'),
]
# USE CASES intro + headers
P += [
 ('<div class="sec-eyebrow">Proof of concept</div>',
  '<div class="sec-eyebrow">' + bi('Proof of concept','実証実験（PoC）') + '</div>'),
 ('<h2>Two live pilots. One proof layer.</h2>',
  '<h2>' + bi('Two live pilots. One proof layer.','2つの実証。1つの証明レイヤー。') + '</h2>'),
 ('<p class="sec-lede">The same WST infrastructure proves a 1,000-yen box of mikan and a luxury handbag — from the everyday to the high-value. Each physical milestone becomes a signed event, and delivery triggers settlement.</p>',
  '<p class="sec-lede">' + bi('The same WST infrastructure proves a 1,000-yen box of mikan and a luxury handbag — from the everyday to the high-value. Each physical milestone becomes a signed event, and delivery triggers settlement.','同じWSTインフラが、1,000円のみかん1箱から高級ハンドバッグまで——日常品から高付加価値品までを証明します。物理的な各マイルストーンが署名済みイベントとなり、配達が決済を起動します。') + '</p>'),
 ('<span class="ic">🍊</span>Shizuoka Mikan</button>',
  '<span class="ic">🍊</span>' + bi('Shizuoka Mikan','静岡みかん') + '</button>'),
 ('<span class="ic">👜</span>Louis Vuitton · Paris→Tokyo</button>',
  '<span class="ic">👜</span>' + bi('Louis Vuitton · Paris→Tokyo','ルイ・ヴィトン · パリ→東京') + '</button>'),
 ('<span class="uc-chip mikan">Pilot 01 · Traceability + Instant Settlement</span>',
  '<span class="uc-chip mikan">' + bi('Pilot 01 · Traceability + Instant Settlement','実証01 · トレーサビリティ＋即時決済') + '</span>'),
 ('<h3>Shizuoka mikan, proven farm to doorstep</h3>',
  '<h3>' + bi('Shizuoka mikan, proven farm to doorstep','静岡みかん、農園から玄関まで証明') + '</h3>'),
 ('<p>100 boxes of Shizuoka mikan shipped to Minato, Tokyo. One delivery ID per box, a QR label the farmer, Sagawa, and the recipient can all verify, and a settlement basis generated automatically at every step of the route.</p>',
  '<p>' + bi('100 boxes of Shizuoka mikan shipped to Minato, Tokyo. One delivery ID per box, a QR label the farmer, Sagawa, and the recipient can all verify, and a settlement basis generated automatically at every step of the route.','静岡みかん100箱を東京・港区へ配送。箱ごとに1つの配送ID、農家・佐川・受取人の全員が検証できるQRラベル、そして経路の各段階で自動生成される決済根拠。') + '</p>'),
 ('<span class="uc-chip lux">Pilot 02 · Aura DPP + Provenance Proof</span>',
  '<span class="uc-chip lux">' + bi('Pilot 02 · Aura DPP + Provenance Proof','実証02 · Aura DPP＋来歴証明') + '</span>'),
 ('<h3>A Louis Vuitton bag, Paris → Minato, Tokyo</h3>',
  '<h3>' + bi('A Louis Vuitton bag, Paris → Minato, Tokyo','ルイ・ヴィトンのバッグ、パリ → 東京・港区') + '</h3>'),
 ('<p>Aura\'s Digital Product Passport proves the bag is genuine at the Paris boutique via an NFC/QR scan. WST adds the missing layer — a tamper-evident record of how that genuine bag travelled to Minato, Tokyo — completing the passport journey end to end: scan (Embark), passport (Enrich), claim ownership (Empower), warranty &amp; resale (Enhance).</p>',
  '<p>' + bi('Aura\'s Digital Product Passport proves the bag is genuine at the Paris boutique via an NFC/QR scan. WST adds the missing layer — a tamper-evident record of how that genuine bag travelled to Minato, Tokyo — completing the passport journey end to end: scan (Embark), passport (Enrich), claim ownership (Empower), warranty &amp; resale (Enhance).','AuraのデジタルプロダクトパスポートがNFC/QRスキャンでパリのブティックでバッグの真正性を証明。WSTは欠けていたレイヤー——その本物のバッグが東京・港区までどう運ばれたかの改ざん検知可能な記録——を加え、パスポートの旅を端から端まで完成させます：スキャン(Embark)、パスポート(Enrich)、所有権主張(Empower)、保証・再販(Enhance)。') + '</p>'),
]
# WHY L1 intro
P += [
 ('<div class="sec-eyebrow">Why a Layer 1 — not just Web2</div>',
  '<div class="sec-eyebrow">' + bi('Why a Layer 1 — not just Web2','なぜLayer 1か——単なるWeb2ではなく') + '</div>'),
 ('<h2>Web2 is for operations. L1 is for trust.</h2>',
  '<h2>' + bi('Web2 is for operations. L1 is for trust.','Web2は運用のため。L1は信頼のため。') + '</h2>'),
 ('<p class="sec-lede">A Web2 tracking system ultimately asks partners to "trust our database." WST records each logistics event so a third party can verify it later, by transaction hash — no trust required.</p>',
  '<p class="sec-lede">' + bi('A Web2 tracking system ultimately asks partners to "trust our database." WST records each logistics event so a third party can verify it later, by transaction hash — no trust required.','Web2の追跡システムは結局、パートナーに「我々のデータベースを信頼してほしい」と求めます。WSTは各物流イベントを記録し、第三者がトランザクションハッシュで後から検証できます——信頼は不要です。') + '</p>'),
]
# Q&A intro + 13 questions
P += [
 ('<div class="sec-eyebrow">From the SGH review</div>',
  '<div class="sec-eyebrow">' + bi('From the SGH review','SGHレビューより') + '</div>'),
 ('<h2>Questions, answered.</h2>',
  '<h2>' + bi('Questions, answered.','質問に、回答します。') + '</h2>'),
 ('<p class="sec-lede">The thirteen technical questions raised during the SGH evaluation, with direct answers grounded in the WST architecture.</p>',
  '<p class="sec-lede">' + bi('The thirteen technical questions raised during the SGH evaluation, with direct answers grounded in the WST architecture.','SGH評価時に挙がった13の技術的質問に、WSTアーキテクチャに基づいて直接回答します。') + '</p>'),
]
QA = [
 ('Can one box hold many product IDs?','1つの箱に複数の製品IDを入れられますか？'),
 ('No scanners today — what about field workload?','現状スキャナーがない——現場の負担は？'),
 ('Can LVMH and SGH choose what to share?','LVMHとSGHは共有範囲を選べますか？'),
 ('This works in Web2 — why own an L1?','Web2で実現できる——なぜL1を持つのか？'),
 ('How is credibility established with LVMH?','LVMHに対する信頼性はどう確立しますか？'),
 ("Beyond winning LVMH, where's the revenue?",'LVMH獲得の先に、収益はどこに？'),
 ("What if competing carriers use SGH's L1?",'競合キャリアがSGHのL1を使ったら？'),
 ('What data can SGH analyze after the PoC?','PoC後、SGHはどんなデータを分析できますか？'),
 ('Is horizontal expansion just adding servers?','横展開はサーバーを足すだけですか？'),
 ('What apps are needed on top of the L1?','L1の上にどんなアプリが必要ですか？'),
 ('Can you build the apps — and what does the PoC cost?','アプリは構築できますか——PoCの費用は？'),
 ('What exactly is the product ID?','製品IDとは正確には何ですか？'),
 ('If the product ID proves authenticity, why a logistics ID?','製品IDで真正性を証明できるなら、なぜ物流IDが必要？'),
]
for en, ja in QA:
    P.append(('<span class="txt">%s</span>' % en, '<span class="txt">%s</span>' % bi(en, ja)))

# ROADMAP intro + phases
P += [
 ('<div class="sec-eyebrow">Phased rollout</div>',
  '<div class="sec-eyebrow">' + bi('Phased rollout','段階的展開') + '</div>'),
 ('<h2>Start small. Prove value. Own the standard.</h2>',
  '<h2>' + bi('Start small. Prove value. Own the standard.','小さく始め、価値を証明し、標準を所有する。') + '</h2>'),
 ('<p class="sec-lede">From a one-month mikan pilot to a logistics proof platform SGH offers to outside companies — each phase de-risks the next.</p>',
  '<p class="sec-lede">' + bi('From a one-month mikan pilot to a logistics proof platform SGH offers to outside companies — each phase de-risks the next.','1か月のみかん実証から、SGHが外部企業に提供する物流証明プラットフォームへ——各フェーズが次のリスクを下げます。') + '</p>'),
 ('<h4>Mikan PoC</h4>', '<h4>' + bi('Mikan PoC','みかんPoC') + '</h4>'),
 ('<p>Shizuoka mikan traceability + settlement simulation.</p>',
  '<p>' + bi('Shizuoka mikan traceability + settlement simulation.','静岡みかんのトレーサビリティ＋決済シミュレーション。') + '</p>'),
 ('<span class="tag">Now</span>', '<span class="tag">' + bi('Now','現在') + '</span>'),
 ('<h4>Premium goods</h4>', '<h4>' + bi('Premium goods','プレミアム商品') + '</h4>'),
 ('<p>Luxury fruit, chilled, furusato-nozei gifts.</p>',
  '<p>' + bi('Luxury fruit, chilled, furusato-nozei gifts.','高級果物・冷蔵・ふるさと納税ギフト。') + '</p>'),
 ('<h4>High-value</h4>', '<h4>' + bi('High-value','高付加価値品') + '</h4>'),
 ('<p>Pharma, cosmetics, and LVMH luxury goods.</p>',
  '<p>' + bi('Pharma, cosmetics, and LVMH luxury goods.','医薬品・化粧品・LVMHの高級品。') + '</p>'),
 ('<h4>Settlement</h4>', '<h4>' + bi('Settlement','決済') + '</h4>'),
 ('<p>Driver &amp; partner settlement integration.</p>',
  '<p>' + bi('Driver &amp; partner settlement integration.','ドライバー・パートナー決済の統合。') + '</p>'),
 ('<h4>Instant pay</h4>', '<h4>' + bi('Instant pay','即時支払い') + '</h4>'),
 ('<p>Stablecoin or bank-API real-time settlement.</p>',
  '<p>' + bi('Stablecoin or bank-API real-time settlement.','ステーブルコインまたは銀行APIによるリアルタイム決済。') + '</p>'),
 ('<h4>Platform</h4>', '<h4>' + bi('Platform','プラットフォーム') + '</h4>'),
 ('<p>Offered to outside companies as proof infra.</p>',
  '<p>' + bi('Offered to outside companies as proof infra.','証明インフラとして外部企業に提供。') + '</p>'),
]
# CTA
P += [
 ('<h2>Turn the proof layer into a pilot.</h2>',
  '<h2>' + bi('Turn the proof layer into a pilot.','証明レイヤーを実証実験へ。') + '</h2>'),
 ('<p>WST is the first step toward SGH owning Japan\'s logistics trust infrastructure — beginning with a low-risk, real-world delivery pilot that keeps field load light while proving the full model.</p>',
  '<p>' + bi('WST is the first step toward SGH owning Japan\'s logistics trust infrastructure — beginning with a low-risk, real-world delivery pilot that keeps field load light while proving the full model.','WSTは、SGHが日本の物流信頼インフラを所有するための第一歩です——現場の負担を抑えつつモデル全体を証明する、低リスクで実地の配送実証から始めます。') + '</p>'),
 ('class="btn btn-teal">Request the PoC brief',
  'class="btn btn-teal">' + bi('Request the PoC brief','PoC概要を請求')),
 ('<a href="#token" class="btn btn-out">Review token details</a>',
  '<a href="#token" class="btn btn-out">' + bi('Review token details','トークン詳細を確認') + '</a>'),
 ('<div class="sec-eyebrow" style="color:var(--teal)">Next step</div>',
  '<div class="sec-eyebrow" style="color:var(--teal)">' + bi('Next step','次のステップ') + '</div>'),
]
# FOOTER
P += [
 ('<p class="foot-about">The proof layer for physical logistics. WST records every delivery milestone as a signed, tamper-evident event on FME Layer 1 — built for Sagawa Holdings, interoperable with Aura DPP and Avery Dennison RFID/NFC/QR.</p>',
  '<p class="foot-about">' + bi('The proof layer for physical logistics. WST records every delivery milestone as a signed, tamper-evident event on FME Layer 1 — built for Sagawa Holdings, interoperable with Aura DPP and Avery Dennison RFID/NFC/QR.','物流のための証明レイヤー。WSTはあらゆる配達マイルストーンをFME Layer 1上の署名済みで改ざん検知可能なイベントとして記録します——佐川グローバルロジスティクス向けに構築、Aura DPPおよびAvery Dennison RFID/NFC/QRと相互運用。') + '</p>'),
 ('<h5>Explore</h5>', '<h5>' + bi('Explore','見る') + '</h5>'),
 ('<h5>Contracts · FME L1</h5>', '<h5>' + bi('Contracts · FME L1','コントラクト · FME L1') + '</h5>'),
 ('<a href="#token">Token spec</a>', '<a href="#token">' + bi('Token spec','トークン仕様') + '</a>'),
 ('<a href="#usecases">Use cases</a>', '<a href="#usecases">' + bi('Use cases','ユースケース') + '</a>'),
 ('<a href="#contact">Contact</a>', '<a href="#contact">' + bi('Contact','お問い合わせ') + '</a>'),
]

missing = []
for old, new in P:
    if old in s:
        s = s.replace(old, new)   # all occurrences (nav/footer dupes handled)
    else:
        missing.append(old[:60])

open(F, "w", encoding="utf-8").write(s)
print("OK chars:", len(s), "| pairs:", len(P), "| missing:", len(missing))
for m in missing:
    print("  MISSING:", m)
PYEOF
mkdir -p /root/ayet-backups && cp /var/www/wst.aucfans.com/index.html /root/ayet-backups/wst_index_$(date +%Y%m%d_%H%M%S).html.bak && python3 /tmp/wst_i18n.py && nginx -s reload 2>/dev/null && echo WST_I18N_DONE

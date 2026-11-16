"""
bench_data.py — Labeled benchmark dataset for retrieval evaluation.

5 realistic multi-section documents (webpage-style, ~2000-3000 words total
each with distractor sections), 100 queries with gold sentences.

Query categories:
  - paraphrase : semantically similar, few overlapping tokens (dense territory)
  - keyword    : exact tokens/acronyms/numbers (BM25 territory)
  - distractor : near-miss phrasing similar to wrong sections (reranker territory)
  - mixed      : general questions touching a whole section
"""

# Each doc: webpage-style markdown text. Queries reference sentences in it.

DOCS = {}

DOCS["neural_networks"] = """# Neural Networks

Neural networks are computing systems inspired by biological brains. They learn by adjusting weighted connections between artificial neurons.

## History

The war of ideas in AI ended in 1986 when backpropagation became popular. Researchers could finally train multi-layer models efficiently. Before that, perceptrons could only learn linear boundaries. The 1943 McCulloch-Pitts neuron model was the first mathematical abstraction of a biological neuron. Frank Rosenblatt built the first perceptron hardware in 1958 at Cornell Aeronautical Laboratory.

## Architecture

An LSTM is a recurrent unit with gates that control memory flow. LSTM networks process sequences one token at a time. LSTM cells avoid vanishing gradients through additive state updates. The forget gate decides what information to discard from the cell state. GRU networks simplify LSTM design by merging the forget and input gates.

The transformer removes recurrence entirely. Transformers use self-attention instead of gated memory. Self-attention lets every token attend to every other token directly. Multi-head attention runs several attention operations in parallel. Positional encodings inject word order information into the model.

## Training

Backpropagation computes gradients of the loss with respect to every weight. Gradient descent updates weights in the direction that reduces loss. The learning rate controls how large each weight update step is. Batch normalization stabilizes training by normalizing layer activations. Dropout randomly zeroes neurons during training to prevent overfitting. Adam optimizer combines momentum and adaptive learning rates.

## Applications

Machine translation was revolutionized by transformers in 2017. BERT and GPT are both transformer variants. Modern LLMs scale transformers to billions of parameters. Speech recognition systems use recurrent networks to model audio sequences. Convolutional networks dominate image classification benchmarks. AlphaFold used attention mechanisms to predict protein structures.

## Limitations

Large language models sometimes hallucinate facts that sound plausible. Training frontier models requires enormous compute and energy budgets. Neural networks are vulnerable to adversarial examples crafted with tiny perturbations. Models trained on biased data reproduce and amplify those biases. The black box nature of deep networks makes decisions hard to explain.
"""

DOCS["web_performance"] = """# Web Performance Optimization

Web performance directly affects user retention, conversion rates, and search rankings. A one-second delay can reduce conversions by seven percent.

## Core Web Vitals

Largest Contentful Paint measures when the biggest element becomes visible. A good LCP score is under 2.5 seconds. Cumulative Layout Shift quantifies unexpected visual movement during page load. CLS should stay below 0.1 for a good user experience. Interaction to Next Paint replaced First Input Delay in March 2024. INP measures responsiveness across all user interactions, not just the first.

## Resource Loading

Lazy loading defers offscreen images until the user scrolls near them. The loading attribute on img tags enables native browser lazy loading. Code splitting breaks JavaScript bundles into smaller chunks loaded on demand. Dynamic imports let modules load only when a route is visited. Tree shaking removes unused exports from production bundles. Preload hints tell the browser to fetch critical resources early.

## Caching Strategies

A service worker intercepts network requests and can serve cached responses. The stale-while-revalidate pattern returns cached content instantly while fetching fresh data. ETags let browsers conditionally request resources only when they changed. CDN edge caching brings static assets physically closer to users. Cache-Control max-age defines how long a resource stays fresh without revalidation.

## JavaScript Optimization

The main thread blocks rendering during long JavaScript tasks. Web Workers move heavy computation off the main thread entirely. Debouncing limits how often an expensive handler fires during rapid events. Memoization caches function results to skip repeated expensive calls. Virtual scrolling renders only visible rows in long lists. Bundle analyzers reveal which dependencies contribute the most kilobytes.

## Image and Media

WebP images are typically 25 to 35 percent smaller than equivalent JPEGs. AVIF compression achieves even better ratios for photographic content. Responsive images with srcset serve appropriately sized files per device. Video poster images display instantly before the video codec initializes. Autoplaying muted videos above the fold should always specify dimensions to prevent layout shift.

## Monitoring

Real user monitoring collects performance data from actual visitors. Synthetic monitoring runs scripted page loads from controlled environments. The Performance API exposes high-resolution timing marks in JavaScript. Long Animation Frames API attributes slow frames to specific scripts. Regression alerts catch performance degradation before users complain.
"""

DOCS["marine_biology"] = """# Coral Reef Ecosystems

Coral reefs occupy less than one percent of the ocean floor but support roughly a quarter of all marine species. Reef-building corals are animals, not plants or rocks.

## Symbiosis

Zooxanthellae are photosynthetic algae living inside coral tissue. The algae provide up to 90 percent of the coral's energy through photosynthesis. Corals supply zooxanthellae with nitrogen and a protected environment. This symbiosis only functions in warm, clear, shallow water. When water temperatures rise, corals expel their algae in a process called bleaching.

## Bleaching Events

The 1998 global bleaching event killed 16 percent of the world's corals. Mass bleaching struck the Great Barrier Reef in 2016, 2017, and 2020 back to back. Bleached corals are starving, not dead, and can recover if temperatures fall quickly. Ocean acidification slows the calcification that builds reef skeletons. Thermal stress is tracked using Degree Heating Weeks calculated from satellite sea surface temperatures.

## Reef Structure

Fringing reefs grow directly along coastlines. Barrier reefs are separated from land by deep lagoons. Atolls are ring-shaped reefs enclosing a central lagoon, formed after volcanic islands sink. The Darwin point marks where subsidence outpaces coral growth. Spur and groove formations channel waves and nutrients across reef flats.

## Biodiversity

Parrotfish scrape algae off coral and excrete fine white sand. The bumphead parrotfish can produce over 400 kilograms of sand per year. Cleaner wrasses run cleaning stations where larger fish remove parasites. Crown-of-thorns starfish outbreaks devour coral polyps at alarming rates. Napoleon wrasse can live fifty years and are protogynous hermaphrodites. Cryptic species hide in reef crevices and account for much undiscovered diversity.

## Conservation

Marine protected areas restrict fishing and anchor damage. The Coral Triangle spans six nations and holds the highest reef biodiversity on Earth. Coral gardening fragments resilient colonies and replants them onto damaged reefs. Assisted gene flow introduces heat-tolerant genotypes to vulnerable populations. Acoustic enrichment plays reef sounds to attract fish larvae to degraded areas. Local stressor reduction, like filtering runoff, buys reefs time against warming.
"""

DOCS["digital_payments"] = """# Digital Payments Infrastructure

Digital payment volume exceeded one trillion transactions globally in 2024. The infrastructure beneath a two-second checkout is enormously complex.

## Card Networks

Visa and Mastercard operate as four-party networks linking issuers, acquirers, and merchants. Interchange fees compensate issuing banks and are capped at 0.3 percent for EU consumer cards. Authorization requests travel through network switches in under 300 milliseconds typically. 3D Secure adds step-up authentication for flagged transactions. Tokenization replaces the primary account number with a device-specific surrogate.

## Real-Time Payment Rails

UPI in India processed over 14 billion transactions monthly by 2024. UPI is an interoperable overlay connecting any bank account to any other instantly. Brazil's Pix reached 150 million users within two years of launch. FedNow launched in 2023 as the United States instant payment rail. SEPA Instant covers euro transfers with a ten-second settlement ceiling. Real-time rails operate 24/7, unlike legacy batch settlement systems.

## Security

EMV chip cards generate a unique cryptogram for every transaction. PCI DSS compliance mandates segmentation of cardholder data environments. Point-to-point encryption renders intercepted card data useless to attackers. Behavioral biometrics profiles typing cadence and swipe patterns for fraud detection. Machine learning fraud models evaluate hundreds of features per swipe in milliseconds. Chargeback fraud, also called friendly fraud, costs merchants billions annually.

## Mobile Wallets

Apple Pay and Google Pay use near-field communication with device tokens. Host card emulation lets phones act as contactless cards. QR code payments dominate in markets where NFC terminals are scarce. Super-apps bundle payments inside messaging platforms, as WeChat Pay demonstrates. Offline payment pilots use secure elements to risk-limit transactions without connectivity.

## Regulation

PSD2 in Europe opened bank APIs to licensed third parties through open banking. The revision PSD3 targets harmonization and fraud information sharing. Payment stablecoins raise reserve and audit questions for regulators. Cross-border remittance costs average over six percent, prompting G20 targets. Licensing regimes differ per jurisdiction, complicating global wallet launches. AML rules require suspicious transaction reporting within defined windows.
"""

DOCS["space_telescopes"] = """# Space Telescopes

Space telescopes observe wavelength bands that Earth's atmosphere absorbs or scatters. Leaving the atmosphere costs more but removes seeing limitations entirely.

## Hubble Legacy

Hubble launched in 1990 with a famously flawed primary mirror. A 1993 servicing mission installed corrective optics, essentially eyeglasses. Hubble's deep field exposures revealed thousands of galaxies in seemingly empty sky. The mirror flaw originated from a miscalibrated null corrector during fabrication. Five servicing missions upgraded instruments through 2009. Hubble still operates, complementing newer infrared observatories.

## James Webb Space Telescope

The JWST primary mirror spans 6.5 meters in 18 gold-coated beryllium segments. The mirror folded origami-style to fit inside a five-meter fairing. Webb launched on Christmas Day 2021 from Kourou, French Guiana. It orbits the second Lagrange point, 1.5 million kilometers from Earth. The sunshield keeps instrument temperatures below 40 kelvin. Near-infrared spectroscopy splits light to reveal atmospheric compositions of exoplanets. The MIRI instrument operates at 7 kelvin using a helium refrigerator. Early science targeted the earliest galaxies, whose light has redshifted into infrared.

## Detection Instruments

Charge-coupled devices convert photons into measurable electrical charge. HgCdTe sensors are sensitive in the infrared but must stay cold. Spectrographs disperse light to analyze chemical fingerprints. Coronagraphs block starlight to image planets orbiting nearby stars. Guidance sensors lock onto guide stars with milliarcsecond precision.

## Exoplanet Science

The transit method detects dips in starlight as planets cross their stars. Radial velocity measurements reveal planets through stellar wobble. JWST detected carbon dioxide in the atmosphere of exoplanet WASP-39b. Water vapor signatures have been found in multiple sub-Neptune atmospheres. The TRAPPIST-1 system contains seven Earth-sized planets around an ultra-cool dwarf. Atmospheric escape observations inform which planets might retain surface water.

## Future Missions

The Roman Space Telescope carries a wide field imager launching around 2027. Roman will survey exoplanets using gravitational microlensing. LUVOIR concepts propose segmented mirrors up to 15 meters. The Habitable Worlds Observatory targets direct imaging of Earth analogs. Starshade proposals use a flying occulter flown tens of thousands of kilometers away. Assembly in orbit may overcome launch vehicle fairing limits.
"""

# 100 queries: (query, gold_sentence, doc_key, category)

QUERIES = [
    # --- neural_networks (20) ---
    ("How does memory flow through an LSTM?", "An LSTM is a recurrent unit with gates that control memory flow.", "neural_networks", "paraphrase"),
    ("How does a recurrent cell keep long-term information stable?", "LSTM cells avoid vanishing gradients through additive state updates.", "neural_networks", "paraphrase"),
    ("What was the first mathematical neuron model?", "The 1943 McCulloch-Pitts neuron model was the first mathematical abstraction of a biological neuron.", "neural_networks", "paraphrase"),
    ("Where was perceptron hardware created?", "Frank Rosenblatt built the first perceptron hardware in 1958 at Cornell Aeronautical Laboratory.", "neural_networks", "paraphrase"),
    ("What year did training multi-layer models become practical?", "The war of ideas in AI ended in 1986 when backpropagation became popular.", "neural_networks", "mixed"),
    ("What does the forget gate control?", "The forget gate decides what information to discard from the cell state.", "neural_networks", "keyword"),
    ("GRU vs LSTM gate count", "GRU networks simplify LSTM design by merging the forget and input gates.", "neural_networks", "keyword"),
    ("How does a transformer replace recurrence?", "The transformer removes recurrence entirely.", "neural_networks", "paraphrase"),
    ("Self-attention mechanism", "Self-attention lets every token attend to every other token directly.", "neural_networks", "keyword"),
    ("Purpose of positional encodings", "Positional encodings inject word order information into the model.", "neural_networks", "keyword"),
    ("How do attention heads parallelize?", "Multi-head attention runs several attention operations in parallel.", "neural_networks", "paraphrase"),
    ("What does dropout do during training?", "Dropout randomly zeroes neurons during training to prevent overfitting.", "neural_networks", "paraphrase"),
    ("What controls the size of a weight update?", "The learning rate controls how large each weight update step is.", "neural_networks", "paraphrase"),
    ("How does batch normalization help?", "Batch normalization stabilizes training by normalizing layer activations.", "neural_networks", "mixed"),
    ("Adam optimizer features", "Adam optimizer combines momentum and adaptive learning rates.", "neural_networks", "keyword"),
    ("Which protein structure project used attention?", "AlphaFold used attention mechanisms to predict protein structures.", "neural_networks", "keyword"),
    ("What are hallucinations in LLMs?", "Large language models sometimes hallucinate facts that sound plausible.", "neural_networks", "mixed"),
    ("Compute demands of frontier models", "Training frontier models requires enormous compute and energy budgets.", "neural_networks", "paraphrase"),
    ("How do adversarial examples attack models?", "Neural networks are vulnerable to adversarial examples crafted with tiny perturbations.", "neural_networks", "mixed"),
    ("Why are deep nets hard to interpret?", "The black box nature of deep networks makes decisions hard to explain.", "neural_networks", "paraphrase"),

    # --- web_performance (20) ---
    ("When does the biggest element render?", "Largest Contentful Paint measures when the biggest element becomes visible.", "web_performance", "paraphrase"),
    ("Good LCP threshold", "A good LCP score is under 2.5 seconds.", "web_performance", "keyword"),
    ("What does CLS quantify?", "Cumulative Layout Shift quantifies unexpected visual movement during page load.", "web_performance", "keyword"),
    ("Maximum acceptable layout shift score", "CLS should stay below 0.1 for a good user experience.", "web_performance", "keyword"),
    ("Which metric replaced FID?", "Interaction to Next Paint replaced First Input Delay in March 2024.", "web_performance", "distractor"),
    ("How does INP differ from FID?", "INP measures responsiveness across all user interactions, not just the first.", "web_performance", "distractor"),
    ("How does native lazy loading work?", "The loading attribute on img tags enables native browser lazy loading.", "web_performance", "keyword"),
    ("Splitting bundles per route", "Dynamic imports let modules load only when a route is visited.", "web_performance", "paraphrase"),
    ("Removing unused bundle exports", "Tree shaking removes unused exports from production bundles.", "web_performance", "keyword"),
    ("What do preload hints do?", "Preload hints tell the browser to fetch critical resources early.", "web_performance", "mixed"),
    ("What is a service worker?", "A service worker intercepts network requests and can serve cached responses.", "web_performance", "paraphrase"),
    ("Stale-while-revalidate pattern", "The stale-while-revalidate pattern returns cached content instantly while fetching fresh data.", "web_performance", "keyword"),
    ("How do ETags save bandwidth?", "ETags let browsers conditionally request resources only when they changed.", "web_performance", "paraphrase"),
    ("Purpose of a CDN", "CDN edge caching brings static assets physically closer to users.", "web_performance", "mixed"),
    ("Long tasks and rendering", "The main thread blocks rendering during long JavaScript tasks.", "web_performance", "paraphrase"),
    ("Offloading heavy computation", "Web Workers move heavy computation off the main thread entirely.", "web_performance", "paraphrase"),
    ("How does WebP compare to JPEG?", "WebP images are typically 25 to 35 percent smaller than equivalent JPEGs.", "web_performance", "keyword"),
    ("Responsive images per device", "Responsive images with srcset serve appropriately sized files per device.", "web_performance", "keyword"),
    ("Preventing video layout shift", "Autoplaying muted videos above the fold should always specify dimensions to prevent layout shift.", "web_performance", "mixed"),
    ("Catching slowdowns in production", "Regression alerts catch performance degradation before users complain.", "web_performance", "paraphrase"),

    # --- marine_biology (20) ---
    ("What powers coral energy?", "The algae provide up to 90 percent of the coral's energy through photosynthesis.", "marine_biology", "paraphrase"),
    ("What does the coral give the algae?", "Corals supply zooxanthellae with nitrogen and a protected environment.", "marine_biology", "paraphrase"),
    ("What happens during bleaching?", "When water temperatures rise, corals expel their algae in a process called bleaching.", "marine_biology", "paraphrase"),
    ("1998 bleaching toll", "The 1998 global bleaching event killed 16 percent of the world's corals.", "marine_biology", "keyword"),
    ("Great Barrier Reef bleaching years", "Mass bleaching struck the Great Barrier Reef in 2016, 2017, and 2020 back to back.", "marine_biology", "keyword"),
    ("Can bleached coral survive?", "Bleached corals are starving, not dead, and can recover if temperatures fall quickly.", "marine_biology", "mixed"),
    ("Acidification effect on skeletons", "Ocean acidification slows the calcification that builds reef skeletons.", "marine_biology", "paraphrase"),
    ("How is heat stress measured?", "Thermal stress is tracked using Degree Heating Weeks calculated from satellite sea surface temperatures.", "marine_biology", "keyword"),
    ("Reef along a coastline", "Fringing reefs grow directly along coastlines.", "marine_biology", "keyword"),
    ("How do atolls form?", "Atolls are ring-shaped reefs enclosing a central lagoon, formed after volcanic islands sink.", "marine_biology", "paraphrase"),
    ("Fish that makes sand", "The bumphead parrotfish can produce over 400 kilograms of sand per year.", "marine_biology", "distractor"),
    ("Cleaning stations on reefs", "Cleaner wrasses run cleaning stations where larger fish remove parasites.", "marine_biology", "mixed"),
    ("Coral-eating starfish", "Crown-of-thorns starfish outbreaks devour coral polyps at alarming rates.", "marine_biology", "keyword"),
    ("Long-lived wrasse sex change", "Napoleon wrasse can live fifty years and are protogynous hermaphrodites.", "marine_biology", "distractor"),
    ("What protects reefs from fishing?", "Marine protected areas restrict fishing and anchor damage.", "marine_biology", "paraphrase"),
    ("Where is reef biodiversity highest?", "The Coral Triangle spans six nations and holds the highest reef biodiversity on Earth.", "marine_biology", "keyword"),
    ("Replanting coral fragments", "Coral gardening fragments resilient colonies and replants them onto damaged reefs.", "marine_biology", "mixed"),
    ("Breeding heat tolerance", "Assisted gene flow introduces heat-tolerant genotypes to vulnerable populations.", "marine_biology", "paraphrase"),
    ("Attracting fish with sound", "Acoustic enrichment plays reef sounds to attract fish larvae to degraded areas.", "marine_biology", "paraphrase"),
    ("Buying time against warming", "Local stressor reduction, like filtering runoff, buys reefs time against warming.", "marine_biology", "paraphrase"),

    # --- digital_payments (20) ---
    ("Who pays interchange fees to whom?", "Interchange fees compensate issuing banks and are capped at 0.3 percent for EU consumer cards.", "digital_payments", "keyword"),
    ("Authorization speed through card networks", "Authorization requests travel through network switches in under 300 milliseconds typically.", "digital_payments", "keyword"),
    ("Step-up authentication", "3D Secure adds step-up authentication for flagged transactions.", "digital_payments", "keyword"),
    ("How is card data protected at merchants?", "Tokenization replaces the primary account number with a device-specific surrogate.", "digital_payments", "paraphrase"),
    ("UPI scale", "UPI in India processed over 14 billion transactions monthly by 2024.", "digital_payments", "keyword"),
    ("Is UPI bank-specific?", "UPI is an interoperable overlay connecting any bank account to any other instantly.", "digital_payments", "mixed"),
    ("Brazil's instant payment system", "Brazil's Pix reached 150 million users within two years of launch.", "digital_payments", "keyword"),
    ("US instant payments launch", "FedNow launched in 2023 as the United States instant payment rail.", "digital_payments", "keyword"),
    ("Euro instant settlement ceiling", "SEPA Instant covers euro transfers with a ten-second settlement ceiling.", "digital_payments", "keyword"),
    ("Why real-time rails differ from legacy", "Real-time rails operate 24/7, unlike legacy batch settlement systems.", "digital_payments", "mixed"),
    ("Chip card transaction secrets", "EMV chip cards generate a unique cryptogram for every transaction.", "digital_payments", "keyword"),
    ("Card data environment rules", "PCI DSS compliance mandates segmentation of cardholder data environments.", "digital_payments", "keyword"),
    ("Point-to-point encryption benefit", "Point-to-point encryption renders intercepted card data useless to attackers.", "digital_payments", "paraphrase"),
    ("Passive fraud signals", "Behavioral biometrics profiles typing cadence and swipe patterns for fraud detection.", "digital_payments", "distractor"),
    ("Refund abuse by customers", "Chargeback fraud, also called friendly fraud, costs merchants billions annually.", "digital_payments", "distractor"),
    ("How do tap-to-pay phones work?", "Apple Pay and Google Pay use near-field communication with device tokens.", "digital_payments", "paraphrase"),
    ("Payments where terminals are rare", "QR code payments dominate in markets where NFC terminals are scarce.", "digital_payments", "keyword"),
    ("Open banking directive", "PSD2 in Europe opened bank APIs to licensed third parties through open banking.", "digital_payments", "keyword"),
    ("Remittance cost problem", "Cross-border remittance costs average over six percent, prompting G20 targets.", "digital_payments", "keyword"),
    ("Reporting obligations", "AML rules require suspicious transaction reporting within defined windows.", "digital_payments", "keyword"),

    # --- space_telescopes (20) ---
    ("Why put telescopes in space?", "Space telescopes observe wavelength bands that Earth's atmosphere absorbs or scatters.", "space_telescopes", "paraphrase"),
    ("Hubble's launch flaw", "Hubble launched in 1990 with a famously flawed primary mirror.", "space_telescopes", "mixed"),
    ("How was Hubble's vision fixed?", "A 1993 servicing mission installed corrective optics, essentially eyeglasses.", "space_telescopes", "paraphrase"),
    ("Deep field discoveries", "Hubble's deep field exposures revealed thousands of galaxies in seemingly empty sky.", "space_telescopes", "paraphrase"),
    ("Where did the mirror error come from?", "The mirror flaw originated from a miscalibrated null corrector during fabrication.", "space_telescopes", "keyword"),
    ("JWST mirror size", "The JWST primary mirror spans 6.5 meters in 18 gold-coated beryllium segments.", "space_telescopes", "keyword"),
    ("How did the mirror fit in the rocket?", "The mirror folded origami-style to fit inside a five-meter fairing.", "space_telescopes", "paraphrase"),
    ("JWST launch date", "Webb launched on Christmas Day 2021 from Kourou, French Guiana.", "space_telescopes", "keyword"),
    ("Where does Webb orbit?", "It orbits the second Lagrange point, 1.5 million kilometers from Earth.", "space_telescopes", "keyword"),
    ("How cold are JWST instruments?", "The sunshield keeps instrument temperatures below 40 kelvin.", "space_telescopes", "keyword"),
    ("Exoplanet atmosphere analysis", "Near-infrared spectroscopy splits light to reveal atmospheric compositions of exoplanets.", "space_telescopes", "paraphrase"),
    ("Coldest instrument on Webb", "The MIRI instrument operates at 7 kelvin using a helium refrigerator.", "space_telescopes", "keyword"),
    ("First JWST science targets", "Early science targeted the earliest galaxies, whose light has redshifted into infrared.", "space_telescopes", "mixed"),
    ("How transits find planets", "The transit method detects dips in starlight as planets cross their stars.", "space_telescopes", "paraphrase"),
    ("Finding planets via stellar wobble", "Radial velocity measurements reveal planets through stellar wobble.", "space_telescopes", "keyword"),
    ("CO2 detection milestone", "JWST detected carbon dioxide in the atmosphere of exoplanet WASP-39b.", "space_telescopes", "keyword"),
    ("Seven planets around a cool star", "The TRAPPIST-1 system contains seven Earth-sized planets around an ultra-cool dwarf.", "space_telescopes", "keyword"),
    ("Roman launch timing", "The Roman Space Telescope carries a wide field imager launching around 2027.", "space_telescopes", "keyword"),
    ("Roman's planet survey method", "Roman will survey exoplanets using gravitational microlensing.", "space_telescopes", "paraphrase"),
    ("Blocking starlight for imaging", "Coronagraphs block starlight to image planets orbiting nearby stars.", "space_telescopes", "mixed"),
]

# Documents that are "background noise" — not queried directly but add distractor mass
EXTRA_CORPUS = {
    "cooking_basics": """# Cooking Fundamentals

Salt seasons food and controls osmosis in vegetables. Salting pasta water heavily seasons noodles from within.

## Heat Management

Searing creates Maillard reaction flavors above 140 degrees Celsius. Resting meat redistributes juices after cooking. Carryover cooking raises internal temperature after removal from heat. A reverse sear cooks steak low and slow before a hot finish.

## Techniques

Mise en place means preparing all ingredients before cooking starts. Deglazing dissolves browned fond into a pan sauce. Emulsification suspends fat and water, as in mayonnaise. Blanching sets color and texture before shocking in ice water.

## Ingredients

Acid brightens flat-tasting dishes; a squeeze of lemon fixes many recipes. Umami comes from tomatoes, mushrooms, and aged cheeses. Starch from pasta water binds and thickens sauces naturally.
""",
    "urban_gardening": """# Urban Gardening

Container gardening makes food production possible on balconies and rooftops.

## Soil

Potting mix must drain well; garden soil compacts in containers. Compost supplies slow-release nutrients and beneficial microbes. Worm castings are gentle enough for seedlings.

## Plant Selection

Leafy greens tolerate partial shade better than fruiting crops. Tomatoes need at least six hours of direct sun daily. Herbs like basil and mint thrive in small pots. Dwarf varieties were bred specifically for container culture.

## Watering

Overwatering kills more container plants than underwatering. Checking soil moisture two knuckles deep prevents guesswork. Self-watering planters use wicking reservoirs below the root zone.
""",
}


def get_all_chunks_clean() -> list[str]:
    """All documents joined per-doc, for the NEW chunker (it needs structure)."""
    return list(DOCS.values()) + list(EXTRA_CORPUS.values())


def get_queries() -> list[tuple[str, str, str, str]]:
    return QUERIES

import requests
import pandas as pd
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote
from html import escape

# ======================================
# CONFIGURACOES
# ======================================

CATEGORY_KEYWORDS = {
    "Inteligência Artificial": [
        "inteligência artificial", "artificial intelligence", "IA generativa",
        "generative AI", "GenAI", "machine learning", "deep learning",
        "computer vision", "large language models", "LLM", "multimodal AI",
        "agentes de IA", "AI agents", "AI ethics", "IA responsável", "IA explicável"
    ],
    "Arte + IA": [
        "AI Art", "arte com IA", "arte generativa", "generative art",
        "arte algorítmica", "algorithmic art", "arte computacional", "arte digital",
        "digital art", "new media art", "media art", "creative AI",
        "AI artist", "artificial creativity", "criatividade computacional"
    ],
    "Imagem, vídeo, som": [
        "text-to-image", "image generation", "AI image", "AI video",
        "text-to-video", "video generation", "AI music", "AI audio",
        "voice cloning", "speech synthesis", "music generation", "Runway",
        "Midjourney", "Flux", "Stable Diffusion", "DALL-E"
    ],
    "XR, Imersão e Espaços Digitais": [
        "XR", "extended reality", "virtual reality", "VR", "augmented reality", "AR",
        "mixed reality", "spatial computing", "immersive art", "immersive experience",
        "metaverse", "digital twin", "volumetric capture"
    ],
    "NFTs, Blockchain e Web3": [
        "NFT", "crypto art", "blockchain art", "Web3", "on-chain art",
        "digital collectibles", "generative NFTs", "digital ownership", "tokenized art"
    ],
    "Museus, Exposições e Instituições": [
        "digital exhibition", "AI exhibition", "immersive exhibition",
        "new media exhibition", "museum technology", "museum innovation",
        "media art festival", "digital culture", "electronic art"
    ],
    "Pesquisa Científica": [
        "computational creativity", "human-AI collaboration", "AI and creativity",
        "creative technologies", "digital humanities", "human computer interaction",
        "HCI", "interactive art", "creative coding"
    ],
    "Educação": [
        "AI education", "creative education", "digital literacy",
        "media literacy", "STEAM", "arte e tecnologia", "educação digital"
    ],
    "Políticas Públicas e Regulação": [
        "AI regulation", "AI Act", "copyright AI", "ethical AI",
        "AI governance", "intellectual property AI"
    ],
    "Chamadas e Fomento": [
        "call for artists", "open call", "artist residency", "residência artística",
        "creative technology grant", "innovation grant", "research funding",
        "XR funding", "digital art award"
    ],
    "Empresas e Plataformas": [
        "OpenAI", "Anthropic", "Google DeepMind", "Adobe Firefly", "Runway",
        "Stability AI", "Midjourney", "Meta AI", "NVIDIA", "Unity", "Unreal Engine",
        "Epic Games", "Autodesk", "Blender", "Hugging Face"
    ],
    "Artistas": [
        "Refik Anadol", "Sougwen Chung", "Mario Klingemann", "Anna Ridler",
        "Memo Akten", "Ian Cheng", "Hito Steyerl", "teamLab"
    ],
    "Termos acadêmicos": [
        "creative technologies", "computational aesthetics", "post-digital", "postdigital",
        "human-machine collaboration", "human-AI collaboration", "algorithmic culture",
        "algorithmic aesthetics", "digital materiality", "technological mediation",
        "presence", "embodiment", "interactive systems", "creative computing"
    ],
    "Pesquisa em português": [
        "arte e tecnologia", "arte digital", "arte imersiva", "criatividade computacional",
        "inteligência artificial", "realidade estendida", "realidade virtual",
        "realidade aumentada", "experiência imersiva", "cultura digital",
        "arte generativa", "arte algorítmica", "instalação interativa"
    ],
    "Pesquisa em inglês": [
        "AI Art", "Generative Art", "Creative AI", "Digital Art", "Immersive Art",
        "Media Art", "Computational Creativity", "Interactive Art", "Extended Reality",
        "Creative Technology", "Human-AI Collaboration", "Artificial Creativity",
        "New Media Art", "Digital Culture", "Creative Coding", "Machine Creativity"
    ]
}

DIAS_RETROATIVOS = 360

GOOGLE_NEWS_LANGUAGE = "pt-BR"
BING_NEWS_LANGUAGE = "pt-BR"
TIMEZONE = ZoneInfo("America/Sao_Paulo")
DISPLAY_TIMEZONE = "UTC-3"

def unique_terms(values):

    seen = set()
    cleaned = []

    for value in values:
        term = value.strip()
        if not term:
            continue
        normalized = term.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(term)

    return cleaned

SEARCH_TERMS = []
for category, keywords in CATEGORY_KEYWORDS.items():
    for keyword in unique_terms(keywords):
        SEARCH_TERMS.append((category, keyword))

# ======================================
# COLETA DAS NOTICIAS
# ======================================

data_limite = datetime.now(TIMEZONE) - timedelta(days=DIAS_RETROATIVOS)
data_limite_ts = pd.Timestamp(data_limite)

noticias = []

def montar_query_google(keyword: str) -> str:

    termo = keyword.strip()
    termo_limpo = termo.strip("\"").strip()
    is_frase_exata = (
        (termo.startswith("\"") and termo.endswith("\"") and len(termo) > 2)
        or any(char.isspace() for char in termo_limpo)
    )

    # Termos compostos (ou já entre aspas) são buscados como frase exata.
    if is_frase_exata and termo_limpo:
        return f"\"{termo_limpo}\""

    return termo_limpo

def noticia_corresponde_keyword(titulo: str, keyword: str) -> bool:

    termo = keyword.strip()
    termo_limpo = termo.strip("\"").strip()
    titulo_normalizado = titulo.casefold()
    is_frase_exata = (
        (termo.startswith("\"") and termo.endswith("\"") and len(termo) > 2)
        or any(char.isspace() for char in termo_limpo)
    )

    # Para termos compostos, exigimos frase exata no titulo.
    if is_frase_exata and termo_limpo:
        return termo_limpo.casefold() in titulo_normalizado

    return True

def coletar_noticias_rss(category: str, keyword: str, fonte: str, rss_url: str) -> None:

    try:

        response = requests.get(rss_url, timeout=20, verify=False)

        soup = BeautifulSoup(
            response.content,
            "xml"
        )

        for item in soup.find_all("item"):

            try:

                data_pub = (
                    pd.to_datetime(item.pubDate.text, utc=True)
                    .tz_convert(TIMEZONE)
                )

                if data_pub >= data_limite_ts:

                    titulo = item.title.text.strip()
                    if not noticia_corresponde_keyword(titulo, keyword):
                        continue

                    noticias.append({
                        "Categoria": category,
                        "Palavra-chave": keyword,
                        "Titulo": titulo,
                        "Data": data_pub,
                        "Link": item.link.text.strip()
                    })

            except:
                pass

    except Exception as erro:
        print(f"Erro em '{keyword}' [{category}] ({fonte}): {erro}")

for category, keyword in SEARCH_TERMS:

    query = montar_query_google(keyword)

    google_rss_url = (
        f"https://news.google.com/rss/search?q={quote(query)}"
        f"&hl={GOOGLE_NEWS_LANGUAGE}"
    )

    bing_rss_url = (
        f"https://www.bing.com/news/search?q={quote(query)}"
        "&format=rss"
        f"&setlang={BING_NEWS_LANGUAGE.lower()}"
        f"&mkt={BING_NEWS_LANGUAGE}"
    )

    coletar_noticias_rss(category, keyword, "Google News", google_rss_url)
    coletar_noticias_rss(category, keyword, "Bing News", bing_rss_url)

# ======================================
# DATAFRAME
# ======================================

df = pd.DataFrame(noticias)

if df.empty:
    print("Nenhuma noticia encontrada.")
    raise SystemExit()

df = df.sort_values(
    by="Data",
    ascending=False
)

df["TituloNormalizado"] = (
    df["Titulo"]
    .astype(str)
    .str.strip()
    .str.casefold()
)

# Mantém apenas uma ocorrência por notícia, mesmo que apareça em múltiplas categorias/keywords.
df = df.drop_duplicates(subset=["TituloNormalizado"], keep="first")
df = df.drop(columns=["TituloNormalizado"])

# ======================================
# HTML5 COM DESIGN MODERNO
# ======================================

def formatar_data_pt(dt) -> str:
    meses = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
    }
    dia = dt.day
    mes = meses[dt.month]
    ano = dt.year
    hora = dt.hour
    return f"Data de publicação: {dia} de {mes} de {ano} | às {hora}h"

ultima_atualizacao_curta = datetime.now(TIMEZONE).strftime("%d/%m/%Y")
ultima_atualizacao = datetime.now(TIMEZONE).strftime(
    "%d/%m/%Y %H:%M:%S"
) + f" ({DISPLAY_TIMEZONE})"

cards_html = ""

for idx, (_, row) in enumerate(df.iterrows(), 1):

    titulo = escape(str(row["Titulo"]))
    categoria = escape(str(row["Categoria"]))
    keyword = escape(str(row["Palavra-chave"]))
    data_formatada = formatar_data_pt(row["Data"])
    link = escape(str(row["Link"]))

    cards_html += f"""
    <article class="card" data-category="{categoria}" data-keyword="{keyword}">

        <span class="card-badge">{categoria}</span>

        <a href="{link}" target="_blank" rel="noopener noreferrer" class="card-title-link" title="Abrir noticia">
            <h3 class="card-title">{titulo}</h3>
        </a>

        <div class="card-meta">
            {data_formatada}
        </div>

    </article>
    """

html = f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor de Notícias - LIAITC</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #EAEFF2;
            min-height: 100vh;
            padding: 40px 16px;
            color: #1F1F1F;
        }}

        .container {{
            max-width: 1240px;
            margin: 0 auto;
            background-color: #FFFFFF;
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
        }}

        /* HEADER LAYOUT */
        .header-container {{
            display: flex;
            flex-direction: column;
            gap: 16px;
            margin-bottom: 32px;
        }}

        .header-logo-card {{
            background-color: #D4E627;
            border-radius: 8px;
            padding: 24px;
            display: flex;
            align-items: center;
            color: #1E1E1E;
        }}

        .logo-title {{
            font-size: 1.8rem;
            font-weight: 800;
            letter-spacing: -0.05em;
            margin-right: 16px;
            white-space: nowrap;
        }}

        .logo-divider {{
            width: 1px;
            height: 32px;
            background-color: #1E1E1E;
            opacity: 0.3;
            margin-right: 16px;
        }}

        .logo-subtitle {{
            font-size: 1rem;
            font-weight: 500;
            line-height: 1.4;
        }}

        .header-stats {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}

        .stat-card {{
            background-color: #A5C3E6;
            border-radius: 8px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            color: #1A202C;
        }}

        .stat-label {{
            font-size: 0.8rem;
            font-weight: 500;
            color: #4A5568;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .stat-value {{
            font-size: 1.6rem;
            font-weight: 700;
            color: #1A202C;
        }}

        @media (min-width: 992px) {{
            .header-container {{
                display: grid;
                grid-template-columns: 3fr 1fr 1fr;
            }}
            .header-stats {{
                grid-column: span 2;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
            }}
        }}

        /* EXPLORAR CONTEUDOS */
        .explore-section {{
            margin-bottom: 32px;
        }}

        .explore-title {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #1E1E1E;
            margin-bottom: 4px;
        }}

        .explore-subtitle {{
            font-size: 0.9rem;
            color: #71717A;
            margin-bottom: 16px;
        }}

        .search-input {{
            width: 100%;
            padding: 14px 16px;
            border: 1px solid #E4E4E7;
            border-radius: 8px;
            background-color: #FFFFFF;
            font-size: 1rem;
            color: #18181B;
            outline: none;
            transition: all 0.2s ease;
        }}

        .search-input::placeholder {{
            color: #A1A1AA;
        }}

        .search-input:focus {{
            border-color: #A1A1AA;
            box-shadow: 0 0 0 3px rgba(161, 161, 170, 0.15);
        }}

        .filters-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 16px;
            align-items: center;
        }}

        .filter-pill {{
            background-color: #FFFFFF;
            border: 1px solid #E4E4E7;
            color: #71717A;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;
        }}

        .filter-pill:hover {{
            background-color: #F4F4F5;
            color: #18181B;
            border-color: #D4D4D8;
        }}

        .filter-pill.active {{
            background-color: #D4E627;
            color: #1E1E1E;
            border-color: #D4E627;
            font-weight: 700;
        }}

        .filter-pill.extra-filter {{
            transition: all 0.2s ease;
        }}

        .filter-pill.is-hidden-filter {{
            display: none;
        }}

        .more-filters-btn {{
            background-color: #18181B;
            color: #FFFFFF;
            border: 1px solid #18181B;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .more-filters-btn:hover {{
            background-color: #27272A;
            border-color: #27272A;
        }}

        /* CONTEUDOS ENCONTRADOS SECTION */
        .results-container {{
            background-color: #EFF2F5;
            border-radius: 12px;
            padding: 32px 24px;
            margin-bottom: 40px;
        }}

        .results-title {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #18181B;
            margin-bottom: 4px;
        }}

        .results-subtitle {{
            font-size: 0.9rem;
            color: #71717A;
            margin-bottom: 24px;
        }}

        main {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
        }}

        @media (min-width: 768px) {{
            main {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}

        @media (min-width: 1024px) {{
            main {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}

        /* CARD STYLE */
        .card {{
            background-color: #FFFFFF;
            border-radius: 8px;
            padding: 24px;
            border: 1px solid #E4E4E7;
            display: flex;
            flex-direction: column;
            gap: 12px;
            transition: all 0.2s ease;
        }}

        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        }}

        .card.is-hidden {{
            display: none !important;
        }}

        .card-badge {{
            display: inline-block;
            background-color: #F4F4F5;
            color: #71717A;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 6px 12px;
            border-radius: 4px;
            margin-bottom: 4px;
            align-self: flex-start;
        }}

        .card-title-link {{
            text-decoration: none;
            color: #18181B;
        }}

        .card-title-link:hover {{
            color: #52525B;
        }}

        .card-title {{
            font-size: 1.15rem;
            font-weight: 600;
            line-height: 1.45;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .card-meta {{
            font-size: 0.8rem;
            color: #A1A1AA;
            margin-top: auto;
            border-top: 1px solid #F4F4F5;
            padding-top: 12px;
        }}

        /* PAGINATION */
        .pagination-container {{
            display: flex;
            justify-content: center;
            margin-top: 32px;
        }}

        .view-more-btn {{
            background-color: #18181B;
            color: #FFFFFF;
            border: 1px solid #18181B;
            padding: 12px 32px;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .view-more-btn:hover {{
            background-color: #27272A;
            border-color: #27272A;
        }}

        .view-more-btn.is-hidden {{
            display: none !important;
        }}

        /* NO RESULTS */
        .no-results {{
            background-color: #F4F4F5;
            color: #71717A;
            text-align: center;
            font-weight: 600;
            border-radius: 8px;
            padding: 32px 16px;
            border: 1px dashed #D4D4D8;
        }}

        /* FOOTER */
        footer {{
            text-align: center;
            margin-top: 40px;
            color: #71717A;
            font-size: 0.85rem;
        }}

        @media (max-width: 576px) {{
            body {{
                padding: 12px 8px;
            }}
            .container {{
                padding: 24px 16px;
                border-radius: 12px;
                box-shadow: none;
            }}
            .header-logo-card {{
                padding: 16px;
            }}
            .logo-title {{
                font-size: 1.4rem;
                margin-right: 12px;
            }}
            .logo-divider {{
                height: 24px;
                margin-right: 12px;
            }}
            .logo-subtitle {{
                font-size: 0.85rem;
            }}
            .results-container {{
                padding: 20px 16px;
            }}
        }}
    </style>
</head>
<body>

    <div class="container">
        <!-- HEADER -->
        <header class="header-container">
            <div class="header-logo-card">
                <div class="logo-title">LIAITC</div>
                <div class="logo-divider"></div>
                <div class="logo-subtitle">Laboratório de Inteligência Artificial, Inovação Tecnológica e Criatividade</div>
            </div>
            <div class="header-stats">
                <div class="stat-card">
                    <div class="stat-label">Conteúdos Encontrados</div>
                    <div class="stat-value" id="news-count">{len(df)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Última atualização</div>
                    <div class="stat-value" style="font-size: 1.3rem;">{ultima_atualizacao_curta}</div>
                </div>
            </div>
        </header>

        <!-- EXPLORAR CONTEUDOS -->
        <section class="explore-section">
            <h2 class="explore-title">Explorar conteúdos</h2>
            <p class="explore-subtitle">Busque por título, categoria, palavras-chave ou temas relacionados.</p>
            <input id="news-search" class="search-input" type="text" placeholder="Digite sua busca" list="keyword-suggestions" autocomplete="off">
            <datalist id="keyword-suggestions"></datalist>
            <div id="category-filters" class="filters-container"></div>
        </section>

        <!-- CONTEUDOS ENCONTRADOS -->
        <section class="results-container">
            <h2 class="results-title">Conteúdos encontrados</h2>
            <p class="results-subtitle">Resultados organizados a partir dos filtros acima.</p>
            
            <p id="no-results-message" class="no-results" hidden>Nenhuma notícia encontrada.</p>

            <main>
                {cards_html}
            </main>

            <div class="pagination-container">
                <button id="view-more-btn" class="view-more-btn">Ver mais</button>
            </div>
        </section>

        <footer>
            <p>Monitor de notícias automático • Atualizado em {ultima_atualizacao}</p>
        </footer>
    </div>

    <script>
        const searchInput = document.getElementById("news-search");
        const suggestionsList = document.getElementById("keyword-suggestions");
        const cards = Array.from(document.querySelectorAll("main .card"));
        const noResultsMessage = document.getElementById("no-results-message");
        const newsCount = document.getElementById("news-count");
        const categoryFilters = document.getElementById("category-filters");
        const viewMoreBtn = document.getElementById("view-more-btn");

        const CARDS_PER_PAGE = 9;
        let visibleCount = CARDS_PER_PAGE;
        let activeCategory = "";

        const normalizeText = (value) => value.toLocaleLowerCase("pt-BR");

        // Collect suggestion terms and unique categories
        const suggestionMap = new Map();
        const categorySet = new Set();
        for (const card of cards) {{
            const keyword = card.dataset.keyword?.trim();
            const category = card.dataset.category?.trim();

            if (keyword) {{
                const normalizedKeyword = normalizeText(keyword);
                if (!suggestionMap.has(normalizedKeyword)) {{
                    suggestionMap.set(normalizedKeyword, keyword);
                }}
            }}

            if (category) {{
                categorySet.add(category);
                const normalizedCategory = normalizeText(category);
                if (!suggestionMap.has(normalizedCategory)) {{
                    suggestionMap.set(normalizedCategory, category);
                }}
            }}
        }}

        // Populate search datalist
        Array.from(suggestionMap.values())
            .sort((a, b) => a.localeCompare(b, "pt-BR", {{ sensitivity: "base" }}))
            .forEach((term) => {{
                const option = document.createElement("option");
                option.value = term;
                suggestionsList.appendChild(option);
            }});

        // Render dynamic category filter buttons
        const renderCategoryButtons = () => {{
            const categories = Array.from(categorySet)
                .sort((a, b) => a.localeCompare(b, "pt-BR", {{ sensitivity: "base" }}));

            categoryFilters.innerHTML = "";

            // "TODOS" button
            const allButton = document.createElement("button");
            allButton.type = "button";
            allButton.className = "filter-pill active";
            allButton.textContent = "TODOS";
            allButton.dataset.category = "";
            categoryFilters.appendChild(allButton);

            // Render categories
            categories.forEach((category, index) => {{
                const button = document.createElement("button");
                button.type = "button";
                button.dataset.category = category;
                button.textContent = category;

                // Show first 5 and hide the rest under "Mais filtros"
                if (index >= 5) {{
                    button.className = "filter-pill extra-filter is-hidden-filter";
                }} else {{
                    button.className = "filter-pill";
                }}
                categoryFilters.appendChild(button);
            }});

            // Add "Mais filtros" button if needed
            if (categories.length > 5) {{
                const moreBtn = document.createElement("button");
                moreBtn.type = "button";
                moreBtn.className = "more-filters-btn";
                moreBtn.textContent = "Mais filtros";
                moreBtn.addEventListener("click", () => {{
                    const extraPills = categoryFilters.querySelectorAll(".extra-filter");
                    const isHidden = extraPills[0].classList.contains("is-hidden-filter");
                    extraPills.forEach(pill => {{
                        pill.classList.toggle("is-hidden-filter", !isHidden);
                    }});
                    moreBtn.textContent = isHidden ? "Menos filtros" : "Mais filtros";
                }});
                categoryFilters.appendChild(moreBtn);
            }}
        }};

        renderCategoryButtons();

        // Filtering and Pagination Logic
        const applyFilter = () => {{
            const filterText = normalizeText(searchInput.value.trim());
            const matchingCards = [];

            // Filter all cards first
            for (const card of cards) {{
                const title = card.querySelector(".card-title")?.textContent ?? "";
                const keyword = card.dataset.keyword ?? "";
                const category = card.dataset.category ?? "";
                const searchableText = normalizeText(`${{title}} ${{keyword}} ${{category}}`);
                
                const textMatch = !filterText || searchableText.includes(filterText);
                const categoryMatch = !activeCategory || normalizeText(category) === normalizeText(activeCategory);

                if (textMatch && categoryMatch) {{
                    matchingCards.push(card);
                }} else {{
                    card.classList.add("is-hidden");
                }}
            }}

            // Update found counter
            newsCount.textContent = String(matchingCards.length);

            // Paginate results
            const totalMatches = matchingCards.length;
            const paginatedCards = matchingCards.slice(0, visibleCount);

            for (const card of paginatedCards) {{
                card.classList.remove("is-hidden");
            }}

            for (let i = visibleCount; i < totalMatches; i++) {{
                matchingCards[i].classList.add("is-hidden");
            }}

            // Show/hide view more button
            if (totalMatches > visibleCount) {{
                viewMoreBtn.classList.remove("is-hidden");
            }} else {{
                viewMoreBtn.classList.add("is-hidden");
            }}

            noResultsMessage.hidden = totalMatches > 0;
        }};

        viewMoreBtn.addEventListener("click", () => {{
            visibleCount += CARDS_PER_PAGE;
            applyFilter();
        }});

        searchInput.addEventListener("input", () => {{
            visibleCount = CARDS_PER_PAGE;
            applyFilter();
        }});

        categoryFilters.addEventListener("click", (event) => {{
            const button = event.target.closest(".filter-pill");
            if (!button || button.classList.contains("more-filters-btn")) {{
                return;
            }}

            activeCategory = button.dataset.category ?? "";

            for (const item of categoryFilters.querySelectorAll(".filter-pill")) {{
                if (!item.classList.contains("more-filters-btn")) {{
                    item.classList.toggle("active", item === button);
                }}
            }}

            visibleCount = CARDS_PER_PAGE;
            applyFilter();
        }});

        // Run initial filter to paginate
        applyFilter();
    </script>
</body>
</html>
"""

arquivo_html = "index.html"

with open(
    arquivo_html,
    "w",
    encoding="utf-8"
) as f:

    f.write(html)

print(f"Sucesso! HTML gerado : {arquivo_html}")
print(f"Sucesso! Noticias encontradas: {len(df)}")

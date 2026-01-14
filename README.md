# extraction_for_prospecting

"""
Script para extrair links do Instagram, nomes de usuário e seguidores
a partir de sites listados em uma planilha Excel.

AVISO IMPORTANTE:

- O scraping do Instagram deve ser feito com moderação
- Respeite os termos de serviço do Instagram
- Use delays apropriados entre requisições
- Considere usar a API oficial do Instagram para projetos de maior escala

Requisitos de instalação:
pip install pandas requests beautifulsoup4 playwright openpyxl tldextract lxml
playwright install

Uso:

# Extrair tudo (links + perfil + seguidores)

python extract_instagram_enhanced.py --input sites.xlsx --column "site"

# Apenas links (sem informações de perfil)

python extract_instagram_enhanced.py --input sites.xlsx --column "url" --no-profile-info

# Com delays personalizados

python extract_instagram_enhanced.py --input sites.xlsx --column "site" --instagram-rate-limit 10

# Para testes rápidos

python extract_instagram_enhanced.py --input sites.xlsx --column 0 --limit 10
python extract_instagram_enhanced.py --input sites.xlsx --column "Website" --output resultado.xlsx --limit 10

# Sem Playwright (mais rápido, menos preciso)

python extract_instagram_enhanced.py --input sites.xlsx --column "site" --no-playwright

Autor: Script automatizado para extração de Instagram
Versão: 1.0.0
"""

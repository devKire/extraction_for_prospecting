#!/usr/bin/env python3
"""
Script AVANÇADO para extrair Instagram de URLs.
Versão 8.1.0 - Extrai de links diretos e varre sites para encontrar Instagram

Uso:
    python extract_instagram_advanced.py --input sites.xlsx --column "Website" --output resultado.xlsx

Autor: Script automatizado para extração de Instagram
Versão: 8.1.0
"""

import pandas as pd
import re
import sys
import argparse
import requests
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
from urllib.parse import urlparse, urljoin
import time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdvancedInstagramExtractor:
    """Extrator avançado de Instagram - extrai de links diretos e varre sites."""
    
    def __init__(self, max_depth: int = 2, timeout: int = 10, max_pages: int = 5):
        """
        Inicializa o extrator.
        
        Args:
            max_depth: Profundidade máxima de varredura
            timeout: Timeout para requisições HTTP
            max_pages: Número máximo de páginas a visitar por site
        """
        self.max_depth = max_depth
        self.timeout = timeout
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.visited_urls = set()
        self.instagram_patterns = [
            r'instagram\.com/([a-zA-Z0-9_.]{1,30})',
            r'instagr\.am/([a-zA-Z0-9_.]{1,30})',
            r'https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]{1,30})/?',
            r'/([a-zA-Z0-9_.]{1,30})/?(?:\?.*)?$'  # Para URLs que terminam com username
        ]
        
        # Padrões INVÁLIDOS para nomes de usuário do Instagram
        # Um usuário do Instagram NUNCA vai ter estes termos no nome
        self.invalid_patterns = [
            r'\.com(?:\.br)?',  # .com ou .com.br
            r'gmail',  # gmail
            r'google',  # google
            r'outlook',  # outlook
            r'hotmail',  # hotmail
            r'yahoo',  # yahoo
            r'email',  # email
            r'contact',  # contact
            r'contato',  # contato
            r'info',  # info
            r'admin',  # admin
            r'web',  # web
            r'site',  # site
            r'www',  # www
            r'http',  # http
            r'https',  # https
            r'mailto:',  # mailto:
            r'@gmail\.com',  # @gmail.com
            r'@hotmail\.com',  # @hotmail.com
            r'@outlook\.com',  # @outlook.com
            r'@yahoo\.com',  # @yahoo.com
            r'\?',  # contém ?
            r'\&',  # contém &
            r'=',  # contém =
            r'%',  # contém %
            r'\s+',  # contém espaços (já validado pelo padrão principal)
        ]
    
    def extract_instagram_info(self, url: str) -> Dict[str, Any]:
        """
        Extrai informações do Instagram de forma avançada.
        
        Args:
            url: URL para processar
            
        Returns:
            Dicionário com informações do Instagram
        """
        result = {
            'original_url': url,
            'instagram_url': '',
            'instagram_username': '',
            'status': 'no_instagram',
            'notes': '',
            'pages_scanned': 0,
            'found_on_page': ''
        }
        
        if not url or pd.isna(url) or str(url).strip() == '':
            result['status'] = 'empty'
            return result
        
        url_str = str(url).strip()
        
        # Remover espaços
        url_str = re.sub(r'\s+', '', url_str)
        
        # 1. Verificar se é link direto do Instagram
        if self._is_direct_instagram_url(url_str):
            normalized_url = self._normalize_instagram_url(url_str)
            result['instagram_url'] = normalized_url
            username = self._extract_username_from_url(normalized_url)
            if username and self._is_valid_instagram_username(username):
                result['instagram_username'] = username
                result['status'] = 'found_direct'
                result['notes'] = 'Link direto do Instagram'
            elif username:
                result['status'] = 'invalid_username'
                result['notes'] = f'Nome de usuário inválido: {username}'
            return result
        
        # 2. Verificar se tem @username no texto (mesmo não sendo URL)
        username_from_text = self._extract_username_from_text(url_str)
        if username_from_text:
            if self._is_valid_instagram_username(username_from_text):
                result['instagram_username'] = username_from_text
                result['instagram_url'] = f'https://www.instagram.com/{username_from_text}/'
                result['status'] = 'found_from_text'
                result['notes'] = 'Extraído de texto com @'
            else:
                result['status'] = 'invalid_username_from_text'
                result['notes'] = f'Nome de usuário inválido extraído de texto: {username_from_text}'
            return result
        
        # 3. Tentar acessar o site e varrê-lo
        try:
            logger.info(f"Iniciando varredura do site: {url_str}")
            instagram_info = self._crawl_site_for_instagram(url_str)
            
            if instagram_info:
                username = instagram_info['username']
                if self._is_valid_instagram_username(username):
                    result['instagram_url'] = instagram_info['url']
                    result['instagram_username'] = username
                    result['status'] = instagram_info['status']
                    result['notes'] = instagram_info.get('notes', '')
                    result['pages_scanned'] = instagram_info.get('pages_scanned', 0)
                    result['found_on_page'] = instagram_info.get('found_on_page', '')
                else:
                    result['status'] = 'invalid_username_crawled'
                    result['notes'] = f'Nome de usuário inválido encontrado: {username}'
                    result['pages_scanned'] = instagram_info.get('pages_scanned', 0)
            else:
                result['status'] = 'not_found_after_scan'
                result['notes'] = f'Varridas {result.get("pages_scanned", 0)} páginas, Instagram não encontrado'
                
        except Exception as e:
            logger.error(f"Erro ao varrer site {url_str}: {e}")
            result['status'] = 'crawl_error'
            result['notes'] = f'Erro na varredura: {str(e)}'
        
        return result
    
    def _is_valid_instagram_username(self, username: str) -> bool:
        """
        Verifica se um nome de usuário do Instagram é válido.
        
        Um usuário do Instagram NUNCA vai ter:
        - .com.br ou .com no nome
        - gmail, google, outlook, hotmail, yahoo
        - email, contact, contato, info, admin
        - web, site, www, http, https
        - mailto:
        - emails completos (@gmail.com, etc.)
        - caracteres especiais como ?, &, =, %
        - espaços (já validado pelo padrão principal)
        
        Args:
            username: Nome de usuário a validar
            
        Returns:
            True se for válido, False se inválido
        """
        username_lower = username.lower()
        
        # Verificar padrões inválidos
        for pattern in self.invalid_patterns:
            if re.search(pattern, username_lower):
                logger.debug(f"Nome de usuário inválido '{username}': contém padrão '{pattern}'")
                return False
        
        # Verificar se parece um email
        if '@' in username and (username.endswith('.com') or username.endswith('.com.br') or 
                              username.endswith('.org') or username.endswith('.net')):
            logger.debug(f"Nome de usuário inválido '{username}': parece um email")
            return False
        
        # Verificar se parece uma URL
        if username.startswith('http://') or username.startswith('https://') or username.startswith('www.'):
            logger.debug(f"Nome de usuário inválido '{username}': parece uma URL")
            return False
        
        # Verificar se é muito longo (mais de 30 caracteres)
        if len(username) > 30:
            logger.debug(f"Nome de usuário inválido '{username}': muito longo ({len(username)} caracteres)")
            return False
        
        # Verificar se contém apenas caracteres permitidos
        if not re.match(r'^[a-zA-Z0-9_.]+$', username):
            logger.debug(f"Nome de usuário inválido '{username}': contém caracteres inválidos")
            return False
        
        return True
    
    def _is_direct_instagram_url(self, url: str) -> bool:
        """Verifica se a URL é um link direto do Instagram."""
        patterns = [
            r'instagram\.com',
            r'instagr\.am',
            r'^@[a-zA-Z0-9_.]+$'
        ]
        
        url_lower = url.lower()
        for pattern in patterns:
            if re.search(pattern, url_lower):
                return True
        
        return False
    
    def _normalize_instagram_url(self, url: str) -> str:
        """Normaliza URL do Instagram."""
        url_lower = url.lower()
        
        # Se começar com @, assume que é username
        if url_lower.startswith('@'):
            username = url_lower[1:].split()[0]
            return f'https://www.instagram.com/{username}/'
        
        # Garantir que começa com https://
        if url_lower.startswith('//'):
            url = 'https:' + url
        elif url_lower.startswith('/'):
            url = 'https://www.instagram.com' + url
        elif not url_lower.startswith('http'):
            url = 'https://' + url
        
        # Remover parâmetros de query desnecessários
        if '?' in url:
            base_url = url.split('?')[0]
            url = base_url.rstrip('/')
        
        return url
    
    def _extract_username_from_url(self, url: str) -> Optional[str]:
        """Extrai username de uma URL do Instagram."""
        for pattern in self.instagram_patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                username = match.group(1)
                # Limpar username
                username = username.split('?')[0]
                username = username.split('#')[0]
                username = username.rstrip('/')
                # Verificar se não é uma página comum
                if username.lower() in ['p', 'explore', 'directory', 'accounts', 'reels', 'stories']:
                    continue
                return username
        
        return None
    
    def _extract_username_from_text(self, text: str) -> Optional[str]:
        """Extrai username do Instagram de um texto."""
        # Padrões comuns de Instagram em texto
        patterns = [
            r'@([a-zA-Z0-9_.]{1,30})(?![a-zA-Z0-9_.])',
            r'instagram\.com/([a-zA-Z0-9_.]{1,30})',
            r'instagr\.am/([a-zA-Z0-9_.]{1,30})',
            r'ig: @?([a-zA-Z0-9_.]{1,30})',
            r'instagram: @?([a-zA-Z0-9_.]{1,30})',
            r'insta: @?([a-zA-Z0-9_.]{1,30})'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                username = match.strip()
                # Validar formato básico
                if re.match(r'^[a-zA-Z0-9_.]{1,30}$', username):
                    return username
        
        return None
    
    def _crawl_site_for_instagram(self, start_url: str) -> Optional[Dict[str, Any]]:
        """
        Varre um site em busca de links do Instagram.
        
        Args:
            start_url: URL inicial para começar a varredura
            
        Returns:
            Informações do Instagram encontradas ou None
        """
        self.visited_urls.clear()
        
        # Tentar normalizar a URL inicial
        if not start_url.startswith(('http://', 'https://')):
            start_url = 'http://' + start_url
        
        urls_to_visit = [(start_url, 0)]  # (url, profundidade)
        pages_scanned = 0
        
        while urls_to_visit and pages_scanned < self.max_pages:
            current_url, depth = urls_to_visit.pop(0)
            
            # Verificar se já visitamos esta URL
            if current_url in self.visited_urls:
                continue
            
            # Verificar profundidade máxima
            if depth > self.max_depth:
                continue
            
            try:
                logger.debug(f"Visitando: {current_url} (profundidade: {depth})")
                response = self.session.get(
                    current_url, 
                    timeout=self.timeout,
                    allow_redirects=True,
                    verify=False
                )
                
                if response.status_code == 200:
                    pages_scanned += 1
                    self.visited_urls.add(current_url)
                    
                    # Buscar Instagram na página atual
                    instagram_info = self._find_instagram_in_page(
                        response.text, 
                        response.url
                    )
                    
                    if instagram_info:
                        instagram_info['pages_scanned'] = pages_scanned
                        instagram_info['found_on_page'] = response.url
                        return instagram_info
                    
                    # Extrair links para visitar (se ainda não atingiu a profundidade máxima)
                    if depth < self.max_depth:
                        new_links = self._extract_links(response.text, response.url)
                        for link in new_links:
                            if link not in self.visited_urls:
                                urls_to_visit.append((link, depth + 1))
                    
                    # Pequena pausa para não sobrecarregar o servidor
                    time.sleep(0.5)
                    
            except Exception as e:
                logger.debug(f"Erro ao acessar {current_url}: {e}")
                continue
        
        return None
    
    def _find_instagram_in_page(self, html: str, page_url: str) -> Optional[Dict[str, Any]]:
        """
        Busca links do Instagram em uma página HTML.
        
        Args:
            html: Conteúdo HTML da página
            page_url: URL da página
            
        Returns:
            Informações do Instagram ou None
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Buscar em todos os links
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            
            # Verificar se é link do Instagram
            if self._is_direct_instagram_url(href):
                normalized_url = self._normalize_url(href, page_url)
                username = self._extract_username_from_url(normalized_url)
                if username and self._is_valid_instagram_username(username):
                    return {
                        'url': normalized_url,
                        'username': username,
                        'status': 'found_in_site',
                        'notes': f'Encontrado em link na página'
                    }
            
            # Verificar texto do link
            link_text = link.get_text(strip=True)
            username = self._extract_username_from_text(link_text)
            if username and self._is_valid_instagram_username(username):
                return {
                    'url': f'https://www.instagram.com/{username}/',
                    'username': username,
                    'status': 'found_in_link_text',
                    'notes': f'Encontrado no texto do link: "{link_text}"'
                }
        
        # 2. Buscar em todo o texto da página
        page_text = soup.get_text()
        username = self._extract_username_from_text(page_text)
        if username and self._is_valid_instagram_username(username):
            return {
                'url': f'https://www.instagram.com/{username}/',
                'username': username,
                'status': 'found_in_page_text',
                'notes': 'Encontrado no texto da página'
            }
        
        # 3. Buscar em meta tags (especialmente Open Graph)
        for meta in soup.find_all('meta'):
            content = meta.get('content', '')
            if content:
                username = self._extract_username_from_text(content)
                if username and self._is_valid_instagram_username(username):
                    return {
                        'url': f'https://www.instagram.com/{username}/',
                        'username': username,
                        'status': 'found_in_meta_tag',
                        'notes': f'Encontrado em meta tag: {meta.get("property", "")}'
                    }
        
        # 4. Buscar em elementos comuns de redes sociais
        social_selectors = [
            '.social-links', '.social-icons', '.social-media',
            '.instagram', '[class*="instagram"]', '[id*="instagram"]',
            '.follow-us', '.social', '.share', '.connect',
            '.instagram', '#instagram', 'a.instagram', 'a[href*="instagram.com"]',
            '[class*="insta"]', '[id*="insta"]',
            '[class*="ig-"]', '[id*="ig-"]', '[class*="ig_"]', '[id*="ig_"]',
            '.social-instagram', '.social__instagram', '.social-link--instagram',
            '.social-icons .instagram', '.social-links .instagram',
            '.follow-instagram', '.follow__instagram', '.follow--instagram',
            '.icon-instagram', '.icon__instagram', '.fa-instagram', '.bi-instagram',
            '[class*="icon-insta"]', '[class*="icon-ig"]', '[class*="fa-instagram"]',
            '.social', '.social-links', '.social-icons', '.follow-us', '.footer-social',
            'a[href*="instagram.com"]',
            'a[title*="instagram"]', 'a[aria-label*="instagram"]',
            'a[data-label*="instagram"]', 'a[data-social*="instagram"]',
            '[class*="instagram-feed"]', '[id*="instagram-feed"]',
            '[class*="insta-feed"]', '[id*="insta-feed"]',
            '[class*="insta-gallery"]', '[id*="insta-gallery"]',
            '[class*="instagram-gallery"]', '[id*="instagram-gallery"]',
            '[class*="instagram-posts"]', '[id*="instagram-posts"]',
            '[class*="elfsight-app"]', '[data-elfsight-app-lazy*="instagram"]',
            '[data-instagram]', '[data-insta]', '[data-feed*="instagram"]',
            '[class*="wp-block-instagram"]', '[class*="elementor-instagram"]',
            '[class*="shopify-section-instagram"]', '[class*="sqs-block-instagram"]',
            'a[href*="instagram.com"][target]', 'a.button[href*="instagram"]',
            'a.btn[href*="instagram"]', 'a.link[href*="instagram"]'
        ]
        
        for selector in social_selectors:
            elements = soup.select(selector)
            for element in elements:
                element_text = element.get_text()
                username = self._extract_username_from_text(element_text)
                if username and self._is_valid_instagram_username(username):
                    return {
                        'url': f'https://www.instagram.com/{username}/',
                        'username': username,
                        'status': 'found_in_social_section',
                        'notes': f'Encontrado na seção: {selector}'
                    }
        
        return None
    
    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """Extrai links de uma página HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            
            # Ignorar links vazios, javascript, mailto, etc.
            if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue
            
            # Normalizar URL
            full_url = self._normalize_url(href, base_url)
            
            # Manter apenas URLs do mesmo domínio
            try:
                base_domain = urlparse(base_url).netloc
                url_domain = urlparse(full_url).netloc
                
                if base_domain and url_domain and base_domain in url_domain:
                    links.add(full_url)
            except:
                pass
        
        return list(links)
    
    def _normalize_url(self, url: str, base_url: str) -> str:
        """Normaliza uma URL relativa para absoluta."""
        if url.startswith('http://') or url.startswith('https://'):
            return url
        elif url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            parsed_base = urlparse(base_url)
            return f'{parsed_base.scheme}://{parsed_base.netloc}{url}'
        else:
            return urljoin(base_url, url)


def process_file_advanced(input_file: str, column_name: str, output_file: str, 
                         max_workers: int = 5, max_depth: int = 2):
    """Processa o arquivo de forma avançada com múltiplas threads."""
    
    logger.info(f"Lendo arquivo: {input_file}")
    
    try:
        df = pd.read_excel(input_file, dtype=str)
        logger.info(f"Arquivo carregado: {len(df)} linhas")
        
        if column_name not in df.columns:
            logger.error(f"Coluna '{column_name}' não encontrada!")
            logger.error(f"Colunas disponíveis: {list(df.columns)}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Erro ao ler arquivo: {e}")
        sys.exit(1)
    
    # Processar cada linha
    logger.info("Processando linhas...")
    logger.info(f"Usando {max_workers} threads, profundidade máxima: {max_depth}")
    
    results = []
    
    def process_row(i, url):
        """Função para processar uma linha individual."""
        extractor = AdvancedInstagramExtractor(max_depth=max_depth)
        result = extractor.extract_instagram_info(url)
        result['row_number'] = i + 1
        result['original_value'] = str(url) if not pd.isna(url) else ''
        return result
    
    # Usar ThreadPoolExecutor para processamento paralelo
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        
        for i, row in df.iterrows():
            url = row[column_name]
            future = executor.submit(process_row, i, url)
            futures.append(future)
        
        # Coletar resultados
        for i, future in enumerate(as_completed(futures)):
            try:
                result = future.result()
                results.append(result)
                
                # Log progresso
                if (i + 1) % 10 == 0:
                    logger.info(f"Processadas {i + 1}/{len(df)} linhas...")
                    
            except Exception as e:
                logger.error(f"Erro ao processar linha {i}: {e}")
    
    # Ordenar resultados pelo número da linha
    results.sort(key=lambda x: x['row_number'])
    
    # Criar DataFrame de saída
    output_df = df.copy()
    
    # Adicionar colunas de resultado
    output_df['Linha'] = [r['row_number'] for r in results]
    output_df['URL_Original'] = [r['original_value'] for r in results]
    output_df['Instagram_URL'] = [r['instagram_url'] for r in results]
    output_df['Instagram_Username'] = [r['instagram_username'] for r in results]
    output_df['Status'] = [r['status'] for r in results]
    output_df['Paginas_Varridas'] = [r.get('pages_scanned', 0) for r in results]
    output_df['Encontrado_Na_Pagina'] = [r.get('found_on_page', '') for r in results]
    output_df['Notas'] = [r.get('notes', '') for r in results]
    
    # Salvar resultados
    logger.info(f"Salvando resultados em: {output_file}")
    
    try:
        output_df.to_excel(output_file, index=False)
        logger.info("Arquivo salvo com sucesso!")
        
        # Gerar relatório
        generate_advanced_report(output_df)
        
    except Exception as e:
        logger.error(f"Erro ao salvar: {e}")
        
        # Tentar CSV
        try:
            csv_file = output_file.replace('.xlsx', '.csv')
            output_df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            logger.info(f"Salvo como CSV: {csv_file}")
        except:
            logger.error("Falha ao salvar")


def generate_advanced_report(df: pd.DataFrame):
    """Gera relatório avançado."""
    
    print("\n" + "=" * 80)
    print("RELATÓRIO - EXTRAÇÃO AVANÇADA DE INSTAGRAM")
    print("=" * 80)
    
    total = len(df)
    
    # Contar por status
    status_counts = df['Status'].value_counts()
    
    print(f"\nTOTAL DE LINHAS: {total}")
    print("\nDISTRIBUIÇÃO POR STATUS:")
    
    for status, count in status_counts.items():
        pct = (count / total) * 100
        print(f"  {status}: {count} ({pct:.1f}%)")
    
    # Mostrar Instagrams encontrados (válidos)
    valid_df = df[df['Instagram_Username'] != '']
    found_count = len(valid_df)
    
    print(f"\nINSTAGRAMS VÁLIDOS ENCONTRADOS: {found_count} ({found_count/total*100:.1f}%)")
    
    if found_count > 0:
        print("\nMÉTODOS DE DESCOBERTA:")
        discovery_stats = valid_df['Status'].value_counts()
        for method, count in discovery_stats.items():
            print(f"  {method}: {count}")
    
    # Estatísticas de varredura
    if 'Paginas_Varridas' in df.columns:
        avg_pages = df['Paginas_Varridas'].mean()
        max_pages = df['Paginas_Varridas'].max()
        print(f"\nESTATÍSTICAS DE VARREDURA:")
        print(f"  Média de páginas varridas por site: {avg_pages:.1f}")
        print(f"  Máximo de páginas varridas: {max_pages}")
    
    # Mostrar exemplos de nomes válidos
    if found_count > 0:
        print("\nEXEMPLOS DE NOMES VÁLIDOS ENCONTRADOS:")
        print("-" * 80)
        
        sample = valid_df.head(5)
        for i, row in sample.iterrows():
            username = row['Instagram_Username']
            status = row['Status']
            original = row['URL_Original'][:50] + "..." if len(row['URL_Original']) > 50 else row['URL_Original']
            notes = row['Notas'][:50] + "..." if len(row['Notas']) > 50 else row['Notas']
            
            print(f"  @{username}")
            print(f"    Original: {original}")
            print(f"    Status: {status}")
            print(f"    Notas: {notes}")
            print()
    
    # Mostrar exemplos de nomes inválidos detectados
    invalid_df = df[df['Status'].str.contains('invalid')]
    if len(invalid_df) > 0:
        print(f"\nNOMES DE USUÁRIO INVÁLIDOS DETECTADOS: {len(invalid_df)}")
        print("-" * 80)
        
        sample = invalid_df.head(5)
        for i, row in sample.iterrows():
            username = row['Instagram_Username']
            if pd.isna(username) or username == '':
                username = 'N/A'
            status = row['Status']
            original = row['URL_Original'][:50] + "..." if len(row['URL_Original']) > 50 else row['URL_Original']
            notes = row['Notas'][:100] + "..." if len(row['Notas']) > 100 else row['Notas']
            
            print(f"  Status: {status}")
            print(f"    Tentativa de username: {username}")
            print(f"    Original: {original}")
            print(f"    Notas: {notes}")
            print()
    
    # Sites que precisaram de varredura
    scanned_sites = df[df['Paginas_Varridas'] > 0]
    if len(scanned_sites) > 0:
        print(f"\nSITES QUE FORAM VARRIDOS: {len(scanned_sites)}")
        success_rate = len(scanned_sites[scanned_sites['Instagram_Username'] != '']) / len(scanned_sites) * 100
        print(f"  Taxa de sucesso na varredura: {success_rate:.1f}%")
    
    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Extrai Instagram de URLs de forma avançada, varrendo sites quando necessário.'
    )
    
    parser.add_argument(
        '--input',
        required=True,
        help='Arquivo Excel de entrada'
    )
    
    parser.add_argument(
        '--column',
        required=True,
        help='Nome da coluna com URLs'
    )
    
    parser.add_argument(
        '--output',
        default='instagram_resultado_avancado.xlsx',
        help='Arquivo de saída'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=5,
        help='Número de threads para processamento paralelo'
    )
    
    parser.add_argument(
        '--depth',
        type=int,
        default=2,
        help='Profundidade máxima de varredura (padrão: 2)'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=5,
        help='Número máximo de páginas a visitar por site'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=10,
        help='Timeout para requisições HTTP em segundos'
    )
    
    args = parser.parse_args()
    
    # Configurações avançadas
    logger.info(f"Configurações: {args.workers} workers, profundidade: {args.depth}, timeout: {args.timeout}s")
    
    process_file_advanced(
        args.input, 
        args.column, 
        args.output,
        max_workers=args.workers,
        max_depth=args.depth
    )


if __name__ == "__main__":
    main()
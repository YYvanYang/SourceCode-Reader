import os
import subprocess
import random
import time
import logging
import configparser
import asyncio
import aiofiles
from ebooklib import epub
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.console import Console
import tempfile
import sys
import chardet

# 在文件顶部添加
MAIN_TEX_TEMPLATE = r"""
\documentclass[a4paper,12pt]{article}

% 导入包配置
\input{templates/latex/includes/packages}

% 文档信息
\title{\Large{$title$}}
\author{$author$}
\date{$date$}

\begin{document}

$if(title)$
\maketitle
\thispagestyle{empty}  % 移除首页页码
$endif$

$body$

\end{document}
"""

PACKAGES_TEX_TEMPLATE = r"""
% 基础包
\usepackage[utf8]{inputenc}
\usepackage{xeCJK}      % 中文支持
\usepackage{graphicx}   % 图片支持
...(您提供的packages.tex的完整内容)...
"""

class ConfigManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

    def get(self, section, key, fallback=None):
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is not None:
                return fallback
            raise

class GitManager:
    def __init__(self):
        self.repo_dir = 'repo'
        os.makedirs(self.repo_dir, exist_ok=True)

    async def clone_repo(self, repo_url):
        """克隆或更新Git仓库"""
        try:
            # 从URL中提取仓库名
            repo_name = repo_url.rstrip('/').split('/')[-1]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            
            full_repo_dir = os.path.join(self.repo_dir, repo_name)
            
            # 如果目录已存在，删除它
            if os.path.exists(full_repo_dir):
                import shutil
                shutil.rmtree(full_repo_dir)
            
            # 克隆仓库
            process = await asyncio.create_subprocess_exec(
                'git', 'clone', repo_url, full_repo_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                print(f"克隆失败: {stderr.decode()}")
                return None
                
            return full_repo_dir
            
        except Exception as e:
            print(f"克隆仓库时发生错误: {str(e)}")
            return None

class DocumentGenerator:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.logger = None
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

    async def create_documents(self, chapters, base_filename):
        """使用pandoc生成文档"""
        try:
            # 添加时间戳到文件名
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_basename = f"{base_filename}_{timestamp}"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # 写入章节文件
                chapter_files = []
                for i, (title, content) in enumerate(chapters):
                    file_path = os.path.join(temp_dir, f"{i:04d}_{title}.md")
                    async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                        await f.write(f"# {title}\n\n```{self._detect_language(title)}\n{content}\n```\n\n")
                    chapter_files.append(file_path)

                # 生成PDF和EPUB
                success_pdf = await self._generate_pdf(chapter_files, output_basename)
                success_epub = await self._generate_epub(chapter_files, output_basename)

                return success_pdf and success_epub

        except Exception as e:
            self.logger.error(f"生成文档时发生错误: {str(e)}")
            return False

    async def _generate_pdf(self, chapter_files, base_filename):
        """生成PDF文档"""
        pdf_output = os.path.join(self.output_dir, f"{base_filename}.pdf")
        
        # 使用 r-string 来处理反斜杠
        today_value = r'\today'
        
        # 从仓库名生成标题（移除时间戳部分）
        repo_name = base_filename.split('_')[0]  # 获取时间戳之前的部分
        default_title = f"{repo_name.replace('-', ' ').title()} 源码阅读笔记"
        
        cmd = [
            "pandoc",
            "--from", "markdown",
            "--to", "pdf",
            "--pdf-engine=xelatex",
            "--highlight-style", "tango",
            "--toc",
            "--toc-depth=2",
            "--template=templates/latex/main.tex",
            "-V", f"title={self.config.get('document', 'title', fallback=default_title)}",
            "-V", f"author={self.config.get('document', 'author', fallback='SourceCode Reader')}",
            "-V", f"date={self.config.get('document', 'date', fallback=today_value)}",
            "-V", f"geometry:margin={self.config.get('document', 'margin', fallback='2.5cm')}",
            "-V", f"mainfont={self.config.get('document', 'mainfont', fallback='Songti SC')}",
            "-V", f"sansfont={self.config.get('document', 'sansfont', fallback='PingFang SC')}",
            "-V", f"monofont={self.config.get('document', 'monofont', fallback='Menlo')}",
            "-o", pdf_output
        ] + chapter_files

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            self.logger.error(f"PDF生成失败: {stderr.decode()}")
            return False

        self.logger.info(f"PDF文档已生成: {pdf_output}")
        return True

    async def _generate_epub(self, md_files, base_filename):
        """使用pandoc生成EPUB"""
        try:
            epub_output = os.path.join(self.output_dir, f"{base_filename}.epub")
            
            cmd = [
                "pandoc",
                "--from", "markdown",
                "--to", "epub",
                "--toc",
                "--toc-depth=2",
                "--epub-chapter-level=1",
                "-o", epub_output
            ] + md_files

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                self.logger.error(f"EPUB生成失败: {stderr.decode()}")
                return False

            self.logger.info(f"EPUB文档已生成: {epub_output}")
            return True

        except Exception as e:
            self.logger.error(f"生成EPUB时发生错误: {str(e)}")
            return False

    def _detect_language(self, filename):
        """根据文件扩展名检测语言"""
        ext = os.path.splitext(filename)[1].lower()
        language_map = {
            # 编程语言
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.rs': 'rust',
            '.go': 'go',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.m': 'objectivec',
            '.mm': 'objectivec',
            '.pl': 'perl',
            '.dart': 'dart',
            '.lua': 'lua',
            '.r': 'r',
            '.ex': 'elixir',
            '.exs': 'elixir',
            '.erl': 'erlang',
            '.hrl': 'erlang',
            '.clj': 'clojure',
            '.fs': 'fsharp',
            '.hs': 'haskell',
            '.ml': 'ocaml',
            '.f90': 'fortran',
            '.jl': 'julia',
            '.pas': 'pascal',
            '.vb': 'vbnet',
            '.asm': 'nasm',
            '.s': 'gas',
            '.el': 'lisp',
            
            # 脚本和配置
            '.sh': 'bash',
            '.ps1': 'powershell',
            '.psm1': 'powershell',
            '.gradle': 'groovy',
            '.sbt': 'scala',
            '.tf': 'hcl',
            '.conf': 'ini',
            '.properties': 'ini',
            
            # 标记和样式
            '.md': 'markdown',
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.sql': 'sql',
            '.css': 'css',
            '.scss': 'scss',
            '.less': 'less',
            '.html': 'html',
            '.htm': 'html',
            '.vue': 'vue',
            
            # 其他
            '.txt': 'text',
            '.vim': 'vim',
        }
        return language_map.get(ext, 'text')  # 默认返回'text'

    def _sanitize_filename(self, filename):
        """清理文件名"""
        # 移除或替换不安全的字符
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        return filename

class EbookCreator:
    def __init__(self, config_manager, logger, git_manager, file_manager, doc_generator):
        self.config_manager = config_manager
        self.logger = logger
        self.git_manager = git_manager
        self.file_manager = file_manager
        self.doc_generator = doc_generator

    async def run(self, progress_callback=None):
        try:
            # 获取仓库URL
            repo_url = self.config_manager.get('github', 'repo_url')
            if not repo_url:
                self.logger.error("未配置GitHub仓库URL")
                return False

            # 克隆仓库
            if progress_callback:
                progress_callback("正在克隆仓库...", 0.1)
            full_repo_dir = await self.git_manager.clone_repo(repo_url)
            if not full_repo_dir:
                return False

            # 获取需要处理的文件
            if progress_callback:
                progress_callback("正在扫描文件...", 0.2)
            files_to_process = self.file_manager._get_files_to_process(
                full_repo_dir,
                self.file_manager.supported_extensions
            )

            # 处理文件
            chapters = []
            total_files = len(files_to_process)
            
            with tqdm(total=total_files, desc="处理文件") as pbar:
                for file_path in files_to_process:
                    result = self.file_manager.process_file(file_path, full_repo_dir)
                    if result:
                        chapter_title, content = result
                        chapters.append((chapter_title, content))
                    pbar.update(1)

            if not chapters:
                self.logger.error("没有找到可处理的文件")
                return False

            # 生成文档
            if progress_callback:
                progress_callback("生成文档...", 0.8)
            
            repo_name = os.path.basename(full_repo_dir)
            await self.doc_generator.create_documents(chapters, repo_name)

            if progress_callback:
                progress_callback("完成", 1.0)

            return True

        except Exception as e:
            self.logger.error(f"发生错误: {str(e)}")
            return False

class FileManager:
    def __init__(self, logger, supported_extensions):
        """初始化文件管理器"""
        self.logger = logger
        self.supported_extensions = supported_extensions
        self.max_files = 50  # 限制最大文件数
        self.max_file_size = 1024 * 1024  # 限制单个文件大小为1MB

    def _get_files_to_process(self, full_repo_dir, supported_extensions):
        """获取需要处理的文件列表"""
        files = []
        file_count = 0
        
        for root, _, filenames in os.walk(full_repo_dir):
            for filename in filenames:
                if file_count >= self.max_files:
                    break
                    
                file_path = os.path.join(root, filename)
                
                # 检查文件大小
                try:
                    if os.path.getsize(file_path) > self.max_file_size:
                        self.logger.debug(f"跳过大文件: {file_path}")
                        continue
                except OSError:
                    continue
                    
                if any(file_path.endswith(ext) for ext in supported_extensions):
                    files.append(file_path)
                    file_count += 1
                    
        return files[:self.max_files]  # 确保不超过最大文件数

    def process_file(self, file_path, full_repo_dir):
        """处理单个文件"""
        try:
            # 检查文件大小
            if os.path.getsize(file_path) > self.max_file_size:
                self.logger.debug(f"文件太大: {file_path}")
                return None
                
            # 检测文件编码
            encoding = self._detect_file_encoding(file_path)
            
            # 读取文件内容
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()

            # 获取相对路径作为标题
            relative_path = os.path.relpath(file_path, start=full_repo_dir)
            chapter_title = relative_path.replace('/', ' > ')

            return chapter_title, content
        except Exception as e:
            self.logger.debug(f"处理文件失败: {file_path}, {str(e)}")
            return None

    def _detect_file_encoding(self, file_path):
        """检测文件编码"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                return result['encoding'] or 'utf-8'
        except Exception:
            return 'utf-8'

async def main():
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # 初始化组件
    config_manager = ConfigManager()
    git_manager = GitManager()
    supported_extensions = config_manager.get('output', 'supported_extensions').split(',')
    file_manager = FileManager(logger, supported_extensions)
    doc_generator = DocumentGenerator(config_manager.get('output', 'output_dir'))
    doc_generator.logger = logger  # 添加logger

    # 创建进度显示
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("正在处理...", total=None)
        
        def update_progress(description, value=None):
            progress.update(task, description=description, completed=value)

        # 创建电子书生成器
        ebook_creator = EbookCreator(
            config_manager=config_manager,
            logger=logger,
            git_manager=git_manager,
            file_manager=file_manager,
            doc_generator=doc_generator
        )

        # 运行转换流程
        success = await ebook_creator.run(progress_callback=update_progress)
        
        if not success:
            logger.error("转换失败")
            return 1
        
        logger.info("转换完成")
        return 0

if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"发生错误: {str(e)}")
        sys.exit(1)

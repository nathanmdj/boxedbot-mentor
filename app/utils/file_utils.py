"""
File processing utilities
"""

import os
import fnmatch
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.core.config import settings
from app.core.logging import LoggerMixin


class FileProcessor(LoggerMixin):
    """Utility class for file processing operations"""
    
    def __init__(self):
        self.supported_extensions = set(settings.SUPPORTED_FILE_EXTENSIONS)
    
    def is_supported_file(self, filename: str) -> bool:
        """Check if file type is supported for analysis"""
        file_ext = self.get_file_extension(filename)
        return file_ext in self.supported_extensions
    
    def get_file_extension(self, filename: str) -> str:
        """Get file extension including the dot"""
        path = Path(filename)
        return path.suffix.lower()
    
    def get_file_language(self, filename: str) -> Optional[str]:
        """Determine programming language from filename"""
        ext = self.get_file_extension(filename)
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.clj': 'clojure',
            '.elm': 'elm',
            '.dart': 'dart',
            '.vue': 'vue',
            '.svelte': 'svelte'
        }
        
        return language_map.get(ext)
    
    def should_skip_file(self, filename: str, file_size: Optional[int] = None) -> bool:
        """Check if file should be skipped based on various criteria"""
        # Skip if not supported
        if not self.is_supported_file(filename):
            return True
        
        # Skip if too large
        if file_size and file_size > settings.MAX_FILE_SIZE_KB * 1024:
            return True
        
        # Skip common patterns that are usually generated or not worth reviewing
        skip_patterns = [
            '*.min.js',
            '*.min.css', 
            '*.bundle.js',
            '*-lock.json',
            '*.lock',
            '*.generated.*',
            '*_pb2.py',  # Protocol buffer generated files
            '*.d.ts',    # TypeScript declaration files (often generated)
        ]
        
        for pattern in skip_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        
        return False
    
    def categorize_file(self, filename: str) -> str:
        """Categorize file by type for focused analysis"""
        filename_lower = filename.lower()
        path_parts = filename.split('/')
        
        # Check for specific directories
        for part in path_parts:
            part_lower = part.lower()
            if part_lower in ['test', 'tests', 'spec', 'specs', '__tests__']:
                return 'test'
            elif part_lower in ['migration', 'migrations']:
                return 'migration'
            elif part_lower in ['auth', 'authentication', 'security']:
                return 'security'
            elif part_lower in ['api', 'endpoint', 'route', 'routes']:
                return 'api'
            elif part_lower in ['model', 'models', 'entity', 'entities']:
                return 'model'
            elif part_lower in ['util', 'utils', 'helper', 'helpers']:
                return 'utility'
            elif part_lower in ['config', 'configuration', 'settings']:
                return 'config'
        
        # Check filename patterns
        if any(pattern in filename_lower for pattern in ['test', 'spec']):
            return 'test'
        elif any(pattern in filename_lower for pattern in ['auth', 'login', 'password']):
            return 'security'
        elif any(pattern in filename_lower for pattern in ['config', 'setting']):
            return 'config'
        elif any(pattern in filename_lower for pattern in ['util', 'helper']):
            return 'utility'
        
        return 'source'
    
    def extract_file_metadata(self, file_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from file data"""
        filename = file_data.get('filename', '')
        
        metadata = {
            'filename': filename,
            'extension': self.get_file_extension(filename),
            'language': self.get_file_language(filename),
            'category': self.categorize_file(filename),
            'size_kb': file_data.get('changes', 0),  # Rough estimate
            'additions': file_data.get('additions', 0),
            'deletions': file_data.get('deletions', 0),
            'is_new_file': file_data.get('status') == 'added',
            'is_deleted': file_data.get('status') == 'removed',
            'is_renamed': file_data.get('status') == 'renamed'
        }
        
        return metadata
    
    def get_focus_areas_by_category(self, category: str) -> List[str]:
        """Get recommended focus areas based on file category"""
        focus_map = {
            'security': ['security', 'maintainability'],
            'test': ['maintainability', 'testing'],
            'api': ['security', 'performance', 'maintainability'],
            'model': ['security', 'performance'],
            'config': ['security', 'maintainability'],
            'migration': ['security'],
            'utility': ['maintainability', 'performance'],
            'source': ['security', 'performance', 'maintainability']
        }
        
        return focus_map.get(category, ['security', 'performance', 'maintainability'])


class DiffParser(LoggerMixin):
    """Utility class for parsing diff content"""
    
    def __init__(self):
        pass
    
    def parse_diff_lines(self, patch: str) -> Dict[str, Any]:
        """Parse diff patch to extract line information"""
        if not patch:
            return {'lines': [], 'added_lines': [], 'removed_lines': [], 'context_lines': []}
        
        lines = patch.split('\n')
        parsed_lines = []
        added_lines = []
        removed_lines = []
        context_lines = []
        
        current_line_old = 0
        current_line_new = 0
        
        for line in lines:
            if line.startswith('@@'):
                # Parse hunk header
                header_info = self._parse_hunk_header(line)
                current_line_old = header_info.get('old_start', 0)
                current_line_new = header_info.get('new_start', 0)
                continue
            
            line_info = {
                'content': line,
                'old_line': current_line_old,
                'new_line': current_line_new,
                'type': 'context'
            }
            
            if line.startswith('+') and not line.startswith('+++'):
                line_info['type'] = 'added'
                line_info['content'] = line[1:]  # Remove the + prefix
                added_lines.append(line_info)
                current_line_new += 1
            elif line.startswith('-') and not line.startswith('---'):
                line_info['type'] = 'removed'
                line_info['content'] = line[1:]  # Remove the - prefix
                removed_lines.append(line_info)
                current_line_old += 1
            else:
                line_info['type'] = 'context'
                context_lines.append(line_info)
                current_line_old += 1
                current_line_new += 1
            
            parsed_lines.append(line_info)
        
        return {
            'lines': parsed_lines,
            'added_lines': added_lines,
            'removed_lines': removed_lines,
            'context_lines': context_lines
        }
    
    def _parse_hunk_header(self, header: str) -> Dict[str, int]:
        """Parse diff hunk header (@@  -old_start,old_count +new_start,new_count @@)"""
        try:
            # Extract the range information
            import re
            match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', header)
            if match:
                old_start = int(match.group(1))
                new_start = int(match.group(3))
                return {
                    'old_start': old_start,
                    'new_start': new_start
                }
        except Exception as e:
            self.log_error("Hunk header parsing", e, header=header)
        
        return {'old_start': 0, 'new_start': 0}
    
    def get_changed_line_numbers(self, patch: str) -> List[int]:
        """Get list of line numbers that were changed"""
        diff_info = self.parse_diff_lines(patch)
        changed_lines = []
        
        for line_info in diff_info['added_lines']:
            if line_info['new_line'] > 0:
                changed_lines.append(line_info['new_line'])
        
        return sorted(set(changed_lines))
    
    def get_context_around_line(self, patch: str, target_line: int, context_size: int = 3) -> str:
        """Get context lines around a specific line number"""
        diff_info = self.parse_diff_lines(patch)
        
        # Find the target line
        target_line_info = None
        for line_info in diff_info['lines']:
            if line_info['new_line'] == target_line:
                target_line_info = line_info
                break
        
        if not target_line_info:
            return ""
        
        # Get context lines
        target_index = diff_info['lines'].index(target_line_info)
        start_index = max(0, target_index - context_size)
        end_index = min(len(diff_info['lines']), target_index + context_size + 1)
        
        context_lines = []
        for i in range(start_index, end_index):
            line_info = diff_info['lines'][i]
            prefix = {
                'added': '+',
                'removed': '-',
                'context': ' '
            }.get(line_info['type'], ' ')
            
            context_lines.append(f"{prefix}{line_info['content']}")
        
        return '\n'.join(context_lines)
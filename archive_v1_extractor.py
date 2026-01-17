#!/usr/bin/env python3

import json
from pathlib import Path
from collections import defaultdict

class ArchonQuestExtractor:
    def __init__(self, data_dir='GenshinScripts/data'):
        self.data_dir = Path(data_dir)
        self.excel_dir = self.data_dir / 'Excel'
        self.textmap_path = self.data_dir / 'TextMap' / 'TextMapCHS.json'
        
        print("Loading data files...")
        self.textmap = self.load_json(self.textmap_path)
        self.chapters = self.load_json(self.excel_dir / 'ChapterExcelConfigData.json')
        self.main_quests = self.load_json(self.excel_dir / 'MainQuestExcelConfigData.json')
        self.quests = self.load_json(self.excel_dir / 'QuestExcelConfigData.json')
        self.talks = self.load_json(self.excel_dir / 'TalkExcelConfigData.json')
        self.dialogs = self.load_json(self.excel_dir / 'DialogExcelConfigData.json')
        self.npcs = self.load_json(self.excel_dir / 'NpcExcelConfigData.json')
        
        self.talk_dict = {t['id']: t for t in self.talks if 'id' in t}
        self.dialog_dict = {}
        for d in self.dialogs:
            dialog_id = d.get('GFLDJMJKIKE') or d.get('id')
            if dialog_id:
                self.dialog_dict[dialog_id] = d
        self.npc_dict = {n['id']: n for n in self.npcs if 'id' in n}
        
        print(f"Loaded: {len(self.chapters)} chapters, {len(self.main_quests)} main quests, {len(self.dialogs)} dialogs")
    
    def load_json(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return []
    
    def get_text(self, hash_value):
        if not hash_value:
            return ""
        return self.textmap.get(str(hash_value), f"[Missing:{hash_value}]")
    
    def get_archon_chapters(self):
        return [ch for ch in self.chapters if ch.get('questType') == 'AQ']
    
    def get_chapter_quests(self, chapter_id):
        return [mq for mq in self.main_quests if mq.get('chapterId') == chapter_id]
    
    def get_quest_talks(self, main_quest_id):
        return [t['id'] for t in self.talks if t.get('questId') == main_quest_id and t.get('id')]
    
    def find_dialog_id(self, init_dialog_id):
        """Maps Talk.initDialog to DialogExcelConfigData.GFLDJMJKIKE.
        Newer game versions require a digit prefix (usually '6') to the initDialog ID."""
        if init_dialog_id in self.dialog_dict:
            return init_dialog_id
        
        for prefix in '0123456789':
            candidate = int(prefix + str(init_dialog_id))
            if candidate in self.dialog_dict:
                return candidate
        
        return None
    
    def extract_dialog_tree(self, dialog_id, visited=None):
        if visited is None:
            visited = set()
        
        real_dialog_id = self.find_dialog_id(dialog_id)
        if real_dialog_id is None or real_dialog_id in visited:
            return []
        
        visited.add(real_dialog_id)
        dialog = self.dialog_dict[real_dialog_id]
        
        role_name = "旁白"
        role_info = dialog.get('talkRole', {})
        if role_info.get('type') == 'TALK_ROLE_NPC' and role_info.get('id'):
            npc_id = int(role_info['id'])
            if npc_id in self.npc_dict:
                npc = self.npc_dict[npc_id]
                role_name = self.get_text(npc.get('nameTextMapHash'))
        elif role_info.get('type') == 'TALK_ROLE_PLAYER':
            role_name = "旅行者"
        
        content = self.get_text(dialog.get('talkContentTextMapHash'))
        
        result = []
        if content:
            result.append({'speaker': role_name, 'content': content, 'id': real_dialog_id})
        
        next_dialogs = dialog.get('nextDialogs', [])
        for next_id in next_dialogs:
            if next_id:
                next_real_id = self.find_dialog_id(next_id)
                if next_real_id and next_real_id not in visited:
                    result.extend(self.extract_dialog_tree(next_id, visited))
        
        return result
    
    def extract_chapter(self, chapter_id):
        chapters = [ch for ch in self.chapters if ch.get('id') == chapter_id]
        if not chapters:
            print(f"Chapter {chapter_id} not found")
            return None
        
        chapter = chapters[0]
        chapter_num = self.get_text(chapter.get('chapterNumTextMapHash'))
        chapter_title = self.get_text(chapter.get('chapterTitleTextMapHash'))
        
        print(f"\n{'='*60}")
        print(f"Extracting: {chapter_num} - {chapter_title} [{chapter_id}]")
        print(f"{'='*60}")
        
        output = []
        output.append(f"{'='*60}")
        output.append(f"{chapter_num}")
        output.append(f"{chapter_title}")
        output.append(f"Chapter ID: {chapter_id}")
        output.append(f"{'='*60}\n")
        
        quests = self.get_chapter_quests(chapter_id)
        print(f"Found {len(quests)} main quests")
        
        for mq in quests:
            mq_title = self.get_text(mq.get('titleTextMapHash'))
            mq_desc = self.get_text(mq.get('descTextMapHash'))
            
            output.append(f"\n{'─'*60}")
            output.append(f"【主线任务】{mq_title} (ID: {mq.get('id')})")
            if mq_desc:
                output.append(f"任务描述：{mq_desc}")
            output.append(f"{'─'*60}\n")
            
            talk_ids = self.get_quest_talks(mq.get('id'))
            print(f"  Quest {mq.get('id')}: {mq_title} - {len(talk_ids)} talks")
            
            for talk_id in talk_ids:
                if talk_id not in self.talk_dict:
                    continue
                
                talk = self.talk_dict[talk_id]
                init_dialog = talk.get('initDialog')
                
                if init_dialog:
                    dialogs = self.extract_dialog_tree(init_dialog)
                    for i, dlg in enumerate(dialogs, 1):
                        output.append(f"{dlg['speaker']}：{dlg['content']}")
                    
                    if dialogs:
                        output.append("")
        
        return '\n'.join(output)
    
    def extract_all_archon_quests(self, chapter_ids, output_dir='output'):
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        all_content = []
        
        for chapter_id in chapter_ids:
            content = self.extract_chapter(chapter_id)
            if content:
                filepath = output_path / f"Chapter_{chapter_id}.txt"
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✓ Saved to {filepath}")
                all_content.append(content)
        
        combined_path = output_path / "ArchonQuest_CHS_AllInOne.txt"
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(all_content))
        print(f"\n✓ Combined file saved to {combined_path}")
        
        return combined_path

if __name__ == '__main__':
    extractor = ArchonQuestExtractor()
    
    archon_chapters = extractor.get_archon_chapters()
    archon_ids = sorted([ch['id'] for ch in archon_chapters])
    
    print(f"\nFound {len(archon_ids)} Archon Quest chapters")
    print(f"IDs: {archon_ids}")
    print(f"\nExtracting all Archon Quest chapters...")
    
    result = extractor.extract_all_archon_quests(archon_ids)
    print(f"\n{'='*60}")
    print("Extraction complete!")
    print(f"{'='*60}")

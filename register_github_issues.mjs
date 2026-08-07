import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const TASKS_DIR = path.join(process.cwd(), 'tasks');
const REPORT_FILE_INSPECT = path.join(process.cwd(), '02_GitHub_Issues_일괄_등록_스크립트_및_라벨_분석.md');
const REPORT_FILE_RESULT = path.join(process.cwd(), '03_GitHub_Issues_일괄_등록_실행_결과.md');

const LABEL_COLORS = {
  'feature': '0366d6',      // Blue
  'backend': '5a32a3',      // Purple
  'frontend': '1d76db',     // Light blue
  'test': '0e8a16',         // Green
  'db': 'b60205',           // Red
  'mock': 'fbca04',         // Yellow
  'priority:high': 'd93f0b',// Dark orange/red
  'priority:medium': 'e99695', // Salmon/pink
  'priority:low': 'c5def5', // Light blue/gray
  'documentation': '0075ca',// Slate Blue
  'bug': 'd73a4a',          // Red
  'refactor': 'e4e669'      // Yellowish green
};

function getLabelColor(label) {
  const clean = label.toLowerCase().trim();
  if (LABEL_COLORS[clean]) return LABEL_COLORS[clean];
  if (clean.includes('priority')) return 'd93f0b';
  if (clean.includes('fe') || clean.includes('frontend') || clean.includes('ui')) return '1d76db';
  if (clean.includes('cmd') || clean.includes('backend') || clean.includes('api')) return '5a32a3';
  if (clean.includes('qry') || clean.includes('query')) return '0052cc';
  if (clean.includes('test') || clean.includes('tc')) return '0e8a16';
  return 'ededed';
}

function getGhCmd() {
  const candidates = [
    'gh',
    'C:\\Program Files\\GitHub CLI\\gh.exe',
    'C:\\Program Files (x86)\\GitHub CLI\\gh.exe',
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'GitHub CLI', 'gh.exe'),
    path.join(process.env.LOCALAPPDATA || '', 'Microsoft', 'WinGet', 'Links', 'gh.exe')
  ];
  for (const cmd of candidates) {
    try {
      const res = spawnSync(cmd, ['--version'], { shell: false });
      if (res.status === 0) return cmd;
    } catch (e) {
      // ignore
    }
  }
  return 'gh';
}

function parseTaskFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split(/\r?\n/);
  
  let inFrontmatter = false;
  let frontmatterEndIndex = -1;
  const meta = { title: '', labels: [], assignees: [] };
  
  if (lines[0] && lines[0].trim() === '---') {
    inFrontmatter = true;
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line === '---') {
        frontmatterEndIndex = i;
        break;
      }
      const match = line.match(/^([a-zA-Z0-9_-]+)\s*:\s*(.*)$/);
      if (match) {
        const key = match[1].toLowerCase();
        let val = match[2].trim();
        val = val.replace(/^['"](.*)['"]$/, '$1');
        
        if (key === 'title') meta.title = val;
        else if (key === 'labels') meta.labels = val ? val.split(',').map(l => l.trim()).filter(Boolean) : [];
        else if (key === 'assignees') meta.assignees = val ? val.split(',').map(a => a.trim()).filter(Boolean) : [];
      }
    }
  }
  
  const body = frontmatterEndIndex !== -1 ? lines.slice(frontmatterEndIndex + 1).join('\n').trim() : content.trim();
  const fileName = path.basename(filePath);
  const taskId = fileName.replace(/\.md$/i, '');
  
  return {
    taskId,
    fileName,
    filePath,
    title: meta.title || `[Task] ${taskId}`,
    labels: meta.labels,
    assignees: meta.assignees,
    body
  };
}

function inspect() {
  console.log('--- [Inspect Mode] Analyzing task markdown files ---');
  const files = fs.readdirSync(TASKS_DIR).filter(f => f.endsWith('.md')).map(f => path.join(TASKS_DIR, f));
  
  const tasks = [];
  const labelSet = new Set();
  
  for (const f of files) {
    const parsed = parseTaskFile(f);
    tasks.push(parsed);
    parsed.labels.forEach(l => labelSet.add(l));
  }
  
  const sortedLabels = Array.from(labelSet).sort();
  console.log(`Total tasks parsed: ${tasks.length}`);
  console.log(`Unique labels found (${sortedLabels.length}):`, sortedLabels.join(', '));
  
  let md = `# [Inspection Report] 66개 Task MD 라벨 추출 및 일괄 등록 스크립트 설계서\n\n`;
  md += `> **작성일시**: ${new Date().toLocaleString()}\n`;
  md += `> **분석 대상**: \`tasks/\` 내 마크다운 파일 ${tasks.length}개\n\n`;
  md += `## 1. 추출된 라벨 (Label Inventory) 및 배정 색상\n\n`;
  md += `이슈 생성 전 아래 라벨들이 GitHub 저장소에 생성됩니다.\n\n`;
  md += `| 라벨명 (Label) | 배정 색상 (Hex) | 설명/카테고리 |\n| :--- | :---: | :--- |\n`;
  
  for (const lbl of sortedLabels) {
    const color = getLabelColor(lbl);
    md += `| \`${lbl}\` | #${color} | ${lbl.includes('priority') ? '우선순위' : lbl.includes('fe') ? '프론트엔드' : lbl.includes('cmd') || lbl.includes('backend') ? '백엔드/코어' : '일반 기능/테스트'} |\n`;
  }
  
  md += `\n## 2. 등록 예정 이슈 목록 요약 (Top 15 및 구조)\n\n`;
  md += `총 ${tasks.length}개의 태스크가 아래의 정제된 메타데이터로 등록됩니다. (YAML 앞쪽 헤더는 본문에서 제거되어 전송됨)\n\n`;
  md += `| Task ID | 파일명 | 추출된 이슈 Title | 적용 라벨 |\n| :--- | :--- | :--- | :--- |\n`;
  
  for (const t of tasks.slice(0, 15)) {
    md += `| **${t.taskId}** | \`${t.fileName}\` | ${t.title} | \`${t.labels.join(', ')}\` |\n`;
  }
  md += `| ... (총 ${tasks.length}개) | ... | ... | ... |\n\n`;
  
  md += `## 3. 다음 실행 안내 (Action Details)\n\n`;
  md += `GitHub CLI(\`gh\`)가 설치되고 \`gh auth login\`으로 인증된 후, 다음 명령어를 실행하면 일괄 등록이 진행됩니다.\n\n`;
  md += `\`\`\`powershell\nnode register_github_issues.mjs --run\n\`\`\`\n\n`;
  md += `- **안정성 보장**: 각 이슈 발급 간 **3.5초의 슬립(Sleep)** 타임이 자동으로 부여되어 GitHub API Rate Limit 및 어뷰징 제재를 원천 방지합니다.\n`;
  md += `- **결과 기록**: 실행 완료 후 등록된 실제 이슈 번호(#ID) 및 웹 링크가 \`03_GitHub_Issues_일괄_등록_실행_결과.md\`로 생성됩니다.\n`;
  
  fs.writeFileSync(REPORT_FILE_INSPECT, md, 'utf-8');
  console.log(`Report successfully generated at: ${REPORT_FILE_INSPECT}`);
}

async function runRegistration() {
  console.log('--- [Run Mode] Registering Labels and Issues to GitHub ---');
  const ghCmd = getGhCmd();
  
  const authCheck = spawnSync(ghCmd, ['auth', 'status'], { encoding: 'utf-8', shell: false });
  if (authCheck.status !== 0) {
    console.error('❌ [Error] GitHub CLI is not authenticated or installed.');
    console.error('Please run "gh auth login" in your terminal first.');
    process.exit(1);
  }
  
  const files = fs.readdirSync(TASKS_DIR).filter(f => f.endsWith('.md')).map(f => path.join(TASKS_DIR, f));
  const tasks = files.map(f => parseTaskFile(f));
  const labelSet = new Set();
  tasks.forEach(t => t.labels.forEach(l => labelSet.add(l)));
  
  console.log('\n[Step 1] Creating / Updating Labels in Repository...');
  for (const lbl of labelSet) {
    const color = getLabelColor(lbl);
    console.log(`  -> Syncing label: ${lbl} (#${color})`);
    spawnSync(ghCmd, ['label', 'create', lbl, '--color', color, '--force'], { shell: false });
  }
  
  console.log('\n[Step 2] Creating GitHub Issues (with 3.5s delay)...');
  const results = [];
  
  for (let i = 0; i < tasks.length; i++) {
    const t = tasks[i];
    console.log(`  [${i+1}/${tasks.length}] Creating Issue: ${t.title}`);
    
    const tempBodyPath = path.join(process.cwd(), `.temp_body_${Date.now()}.md`);
    fs.writeFileSync(tempBodyPath, t.body, 'utf-8');
    
    const args = ['issue', 'create', '--title', t.title, '--body-file', tempBodyPath];
    for (const l of t.labels) {
      args.push('--label', l);
    }
    
    const res = spawnSync(ghCmd, args, { encoding: 'utf-8', shell: false });
    
    if (fs.existsSync(tempBodyPath)) {
      try { fs.unlinkSync(tempBodyPath); } catch(e) {}
    }
    
    if (res.status === 0) {
      const issueUrl = res.stdout.trim();
      const issueNumMatch = issueUrl.match(/\/issues\/(\d+)$/);
      const issueNum = issueNumMatch ? `#${issueNumMatch[1]}` : 'Created';
      console.log(`      ✔ Success: ${issueUrl} (${issueNum})`);
      results.push({ ...t, issueUrl, issueNum, status: 'Success', error: '' });
    } else {
      console.error(`      ❌ Failed: ${res.stderr || res.stdout}`);
      results.push({ ...t, issueUrl: '', issueNum: 'N/A', status: 'Failed', error: (res.stderr || res.stdout).trim() });
    }
    
    if (i < tasks.length - 1) {
      await new Promise(r => setTimeout(r, 3500));
    }
  }
  
  console.log('\n[Step 3] Generating Result Report...');
  let md = `# [Execution Report] GitHub Issues 일괄 등록 최종 결과\n\n`;
  md += `> **실행 일시**: ${new Date().toLocaleString()}\n`;
  md += `> **총 처리 대상**: ${tasks.length}건\n`;
  const successCount = results.filter(r => r.status === 'Success').length;
  md += `> **성공**: ${successCount}건 / **실패**: ${tasks.length - successCount}건\n\n`;
  md += `## 1. 이슈 생성 결과 매핑 테이블\n\n`;
  md += `| Task ID | 파일명 | 등록된 이슈 Title | Issue 번호 & Link | 상태 |\n| :--- | :--- | :--- | :--- | :---: |\n`;
  
  for (const r of results) {
    const linkStr = r.issueUrl ? `[${r.issueNum}](${r.issueUrl})` : `N/A (${r.error})`;
    md += `| **${r.taskId}** | \`${r.fileName}\` | ${r.title} | ${linkStr} | ${r.status === 'Success' ? '🟢 성공' : '🔴 실패'} |\n`;
  }
  
  fs.writeFileSync(REPORT_FILE_RESULT, md, 'utf-8');
  console.log(`\n🎉 Registration finished! See full report at: ${REPORT_FILE_RESULT}`);
}

const mode = process.argv[2] || '--inspect';
if (mode === '--run') {
  runRegistration().catch(e => { console.error(e); process.exit(1); });
} else {
  inspect();
}

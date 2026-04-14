# Music Recommender

分析网易云音乐歌单，推荐符合你口味的歌曲，并提供免费的 Bilibili 播放链接。

## 功能特性

- 🎵 **歌单分析** - 分析网易云音乐歌单，建立用户口味画像
- 🎯 **精准推荐** - 基于口味画像推荐相似歌曲
- 📺 **免费播放** - 提供 Bilibili 免费播放链接（无需会员）
- 📅 **每日推荐** - 每天仅推荐一次，避免重复
- 📊 **历史记录** - 记录所有推荐历史，确保不重复

## 前置要求

### 1. 安装依赖

```bash
pip3 install requests
```

### 2. 准备网易云音乐歌单链接

支持的链接格式：
- `https://music.163.com/playlist?id=XXXXX`
- `https://music.163.com/#/playlist?id=XXXXX`

## 使用方法

### 在 Claude Code 中

```
推荐音乐，基于我的歌单：https://music.163.com/playlist?id=12345
```

```
今日歌单推荐
```

```
分析这个歌单并给我推荐歌曲
```

### 工作流程

1. **解析歌单** - 从链接中提取歌单 ID
2. **分析口味** - 分析歌手、语言、风格、年代、情绪
3. **智能推荐** - 推荐符合口味但不在歌单中的歌曲
4. **搜索链接** - 为每首歌搜索 Bilibili 播放链接
5. **格式化输出** - 按 Telegram 兼容格式输出
6. **记录历史** - 保存推荐历史，避免重复

### 口味分析维度

- **Top 歌手** - 统计最常听的前 10-20 位歌手
- **语言比例** - 中文/英文/日语/韩语比例
- **风格标签** - 气声唱法、90s怀旧、indie folk、dream pop 等
- **年代分布** - 识别歌曲年代分布
- **情绪特征** - upbeat/melancholic/dreamy/energetic

## 输出格式

```
🎵 今日推荐歌单

**华语女声：**
1. 陈粒 — 奇妙能力歌
https://www.bilibili.com/video/BVxxxxx

**欧美梦幻：**
6. Lana Del Rey — Video Games
https://www.bilibili.com/video/BVyyyyy
```

## 历史记录

推荐历史保存在：
```
~/.openclaw/workspace/music-history/
├── 2026-03-29.json
├── 2026-03-30.json
└── ...
```

### 历史管理

```bash
# 查看所有历史
python3 {baseDir}/scripts/history.py show

# 保存今日推荐
python3 {baseDir}/scripts/history.py save
```

## 重要规则

- ✅ 每天仅推荐一次
- ✅ 检查历史，避免重复推荐
- ✅ 使用 Bilibili 链接（免费）
- ✅ 按风格/语言分组输出
- ❌ 不推荐歌单中已有的歌曲

## API 信息

- **网易云音乐 API**: `https://music.163.com/api/v6/playlist/detail?id=<ID>&n=1000`
- **Bilibili 搜索 API**: `https://api.bilibili.com/x/web-interface/search/all/v2?keyword=<query>`

## 额外功能

推荐后可选择：
- 保存到 Notion（内容日历或音乐数据库）
- 生成 HTML 页面
- 创建文本文件

## License

MIT

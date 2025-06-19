# pak.py: The tool that saves you from LLM copy-paste hell

## The problem every developer has (but nobody admits)

It's 2025. You're a programmer using Claude, ChatGPT, or any LLM **every 20 seconds**. Every time, it's the same pain:

- You need to send 5-10 files to the LLM for context
- Open the first file → Ctrl+A → Ctrl+C → go to chat → Ctrl+V
- "Wait, I need to say which file this is"
- Go back → copy the path → paste before the code
- Repeat for every file
- After 10 minutes, your prompt looks like cat vomit
- The LLM replies with modified code
- Now you have to **do it all in reverse**: copy each code block from the LLM and save it in the right file
- You make mistakes, overwrite the wrong version, curse

**This happens 20 times a day.**

If this sounds familiar, pak.py was made for you.

## pak: The solution you wish you invented

pak is a command-line tool that solves **exactly** this problem. Elegantly, quickly, and without hassle.

### The workflow before pak.py
```
1. Open file1.py → copy → paste in chat with "File: file1.py"
2. Open file2.js → copy → paste in chat with "File: file2.js"  
3. Open file3.css → copy → paste in chat with "File: file3.css"
4. Write your question
5. LLM replies with modified code
6. Manually copy each piece and save it in the right file
7. Hope you didn't mess up
```

**Time**: ~15 minutes of boring work  
**Errors**: Guaranteed  
**Frustration**: Maximum

### The workflow with pak.py
```bash
# Package everything
pak.py --compress-level smart src/ > project.pak

# Paste the content of project.pak in chat + your question
# LLM replies with a new .pak file

# Unpack the response
pak.py --unpack response.pak --outdir ./updated
```

**Time**: 30 seconds  
**Errors**: Zero  
**Frustration**: Zero

## How pak.py works in practice

### Real example: Refactoring a React component

You have a directory with these files:
```
src/
├── components/
│   ├── UserCard.jsx
│   ├── UserCard.css
│   └── UserCard.test.js
├── hooks/
│   └── useUser.js
└── utils/
    └── formatters.js
```

**Without pak.py:**
1. Open 5 files
2. Copy-paste each into chat
3. Write: "Convert this component to use TypeScript"
4. LLM replies with 5 code blocks
5. Manually copy each block into the right file
6. Rename files from .js to .ts/.tsx
7. Check for mistakes

**With pak.py:**
```bash
# Package
pak.py --compress-level medium src/ --ext .jsx .js .css > component.pak

# In chat:
# [paste content of component.pak]
# "Convert everything to TypeScript and optimize performance"

# LLM replies with a new .pak file
# Save it as typescript.pak

# Unpack
pak.py --unpack typescript.pak --outdir ./src-updated
```

Result: you get a `src-updated/` directory with all files converted, optimized, and correctly renamed.

### Example 2: Debugging a complex bug

Your Node.js backend has a bug involving multiple files. Instead of copying manually:

```bash
# Package only the relevant files
pak.py --compress-level aggressive \
     server.js \
     routes/auth.js \
     middleware/validation.js \
     models/User.js \
     > bug-context.pak
```

Paste the content in chat + "There's a bug in authentication, users get logged in even if the token is expired."

The LLM sees **all the necessary context** at once and can give a precise answer.

### Example 3: Collaborative code review

Your colleague asks you to review a feature. Instead of sending GitHub links:

```bash
# Package the feature
pak.py --compress-level light feature-branch/ --ext .py .sql > feature-review.pak
```

Send the `.pak` file to your colleague, who can:
1. Read it directly (it's plain text)
2. Unpack it to test locally
3. Send it to the LLM for automatic analysis

## Why pak.py is brilliant for LLM workflows

### 1. **LLM-native format**

The `.pak` format is **designed** to be understood by LLMs:

```
__PAK_FILE_abc123_START__
Path: src/components/Button.jsx
Language: javascript
Size: 1847
Lines: 67
Tokens: 425
Compression: medium
Method: AST-enabled
__PAK_DATA_abc123_START__
import React from 'react';
import './Button.css';

export const Button = ({ children, variant = 'primary', ...props }) => {
  return (
    <button className={`btn btn-${variant}`} {...props}>
      {children}
    </button>
  );
};
__PAK_DATA_abc123_END__
```

The LLM knows **exactly**:
- What file it is
- What language it is
- How big it is  
- How it was compressed

And can **reproduce the same format** when replying.

### 2. **Smart compression**

pak isn't dumb. With `--compress-level smart`:
- **README.md** → keeps everything (important for context)
- **main.py** → keeps everything (main file)
- **utils.py** → compresses comments but keeps logic
- **test_*.py** → compresses aggressively (often you don't need all tests)

### 3. **Automatic token management**

```bash
pak.py --compress-level smart --max-tokens 8000 huge-project/
```

pak **automatically prioritizes** the most important files and stops when the token limit is reached. No more counting characters or worrying about context window overflow.

### 4. **Robust fallback**

If pak.py can't parse a file's AST (for any reason), it **doesn't crash**. It automatically falls back to text compression. Your workflow never breaks.

## Setup: 5 minutes forever

### Installation
```bash
# Download pak.py
curl -O https://raw.githubusercontent.com/pakkio/pak/main/pak.py
chmod +x pak.py
sudo mv pak.py /usr/local/bin/

# Check it works
pak.py --version
```

### Dependencies (optional but recommended)
```bash
# For advanced AST compression
pip3 install --user tree-sitter tree-sitter-languages tree-sitter-python

# Check AST support
pak.py --ast-info
```

If you don't install the Python dependencies, pak.py **still works** with text compression. AST is a bonus, not a requirement.

## Commands you'll actually use

### Basic packaging
```bash
# Whole project
pak.py src/ > project.pak

# Only specific files
pak.py main.py utils.py config.yaml > core.pak

# Only certain file types
pak.py --ext .py .md ./my-project > python-docs.pak
```

### Smart compression
```bash
# Light: removes whitespace and trivial comments
pak.py --compress-level light src/ > light.pak

# Medium: keeps structure but compresses implementations
pak.py --compress-level medium src/ > medium.pak

# Aggressive: only signatures and public API
pak.py --compress-level aggressive src/ > minimal.pak

# Smart: auto-selects based on file importance
pak.py --compress-level smart --max-tokens 12000 src/ > smart.pak
```

### Unpacking
```bash
# In current directory
pak.py --unpack response.pak

# In a specific directory
pak.py --unpack response.pak --outdir ./new-version

# See what's inside before unpacking
pak.py --ls response.pak
```

## Everyday use cases

### 1. **Guided refactoring**
"Take these 10 files and convert them from Class Components to Function Components with hooks"

### 2. **Bug hunting**
"There's a memory leak somewhere in these modules, help me find it"

### 3. **Automatic code review**
"Analyze this pull request and tell me if there are security or performance issues"

### 4. **Automatic documentation**
"Generate API docs for these endpoints"

### 5. **Assisted migration**
"Migrate this project from Python 3.8 to 3.12, update deprecated dependencies"

### 6. **Performance optimization**
"These React components re-render too often, optimize them"

### 7. **Test generation**
"Generate unit tests for all these functions"

### 8. **Architecture review**
"Is this code well structured? Suggest architectural improvements"

## Honest comparisons

### vs. Manual copy-paste
**pak always wins.** No contest.

### vs. Custom script
If you already have a script that does the same and you're happy, keep using it. But pak.py probably handles more edge cases and languages than your script.

### vs. GitHub + LLM links
- **Pro GitHub**: No local setup
- **Pro pak.py**: Works offline, faster, total control over context

### vs. Enterprise tools (LLMLingua, etc.)
- **Pro enterprise**: More mathematically sophisticated compression
- **Pro pak.py**: Free, offline, zero setup, no API dependencies

For daily personal use, pak.py **wins for convenience**.

## Honest limitations

### 1. **Not magic**
If your project has 100k lines of code, pak.py can't compress it into 1000 tokens and keep all context. You need to be selective.

### 2. **Python dependencies for AST**
For advanced compression you need Python + tree-sitter. On very restricted environments you may have to use only text compression.

### 3. **Doesn't replace understanding**
pak helps you **prepare** context for the LLM, but you still need to know **what to ask** and **how to interpret** the answers.

### 4. **Works best on structured projects**
If your code is a total mess with no structure, pak.py can't work miracles in prioritization.

## Tips and tricks

### 1. **Use aliases for common workflows**
```bash
# In your .bashrc/.zshrc
alias pak-quick='pak.py --compress-level smart --max-tokens 8000'
alias pak-review='pak.py --compress-level medium --ext .py .js .ts'
alias pak-minimal='pak.py --compress-level aggressive'
```

### 2. **Combine with other tools**
```bash
# Only recently modified files
git diff --name-only HEAD~5 | xargs pak.py > recent-changes.pak

# Only files containing a certain function  
grep -r "getUserData" src/ | cut -d: -f1 | sort -u | xargs pak.py > user-data-logic.pak
```

### 3. **Templates for common requests**
Create template files to include in your requests:
```bash
pak.py src/ > codebase.pak
cat codebase.pak refactoring-prompt-template.txt > full-request.txt
```

### 4. **Backup before unpacking**
```bash
# Always backup before unpacking over existing code
cp -r src/ src-backup/
pak.py --unpack new-version.pak --outdir src/
```

## Conclusion: The tool you didn't know you needed

pak is one of those tools that seems **obvious after** you use it. You wonder how you lived without it.

It doesn't revolutionize the world. It doesn't use AI. There's no billion-dollar startup behind it.

**It just works.** It solves a daily annoying problem elegantly and reliably.

If you work with LLMs daily, download it. Try it for a week. If it doesn't make your life easier, you've lost 5 minutes. If it does, you've gained hours every week forever.

It's free, it's open source, and your LLM workflow will never be the same.

**Download**: https://github.com/pakkio/pak  
**Setup time**: 5 minutes  
**ROI**: Infinite

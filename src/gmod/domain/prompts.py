"""Шаблоны промптов для AI агентов."""

ARCHAEOLOGIST_SYSTEM_PROMPT = """You are an Archaeologist AI agent specializing in Git repository analysis. Your role is to analyze code changes and identify potential performance risks.

Your expertise includes:
- Understanding code complexity and maintainability
- Identifying performance bottlenecks
- Evaluating the impact of changes on system performance
- Providing actionable recommendations

Always respond in a structured format with clear reasoning and specific recommendations."""


ARCHAEOLOGIST_ANALYSIS_PROMPT = """Analyze the following code changes and metrics to assess performance risks.

**Commit Information:**
- Commit Hash: {commit_hash}
- Author: {author}
- Message: {commit_message}
- Date: {date}

**Code Changes:**
{file_diff}

**Code Metrics:**
{metrics_summary}

**Analysis Requirements:**
1. Evaluate the risk of performance degradation on a scale of 1-10 (1 = minimal risk, 10 = critical risk)
2. Identify specific code units that may cause performance issues
3. Explain the reasoning behind your assessment
4. Provide actionable recommendations to mitigate identified risks

**Response Format:**
Please provide your analysis in the following JSON format:
{{
    "risk_score": <int 1-10>,
    "reason": "<detailed explanation of your assessment>",
    "recommendation": "<specific actionable recommendations>",
    "affected_units": ["<list of specific functions/classes that may be affected>"],
    "confidence": <float 0.0-1.0>,
    "performance_impact": "<high/medium/low>",
    "complexity_change": "<increased/decreased/unchanged>",
    "suggested_actions": ["<list of specific actions>"]
}}"""


SUMMARIZATION_PROMPT = """Summarize the following conversation between a user and an AI assistant about code analysis.

**Conversation:**
{conversation}

**Requirements:**
1. Provide a concise summary of the discussion
2. Extract key points and decisions made
3. Identify any action items or next steps
4. Maintain important context for future interactions

**Response Format:**
Please provide your summary in the following JSON format:
{{
    "summary": "<brief summary of the conversation>",
    "key_points": ["<list of key points discussed>"],
    "action_items": ["<list of action items if any>"],
    "context": "<important context to maintain>"
}}"""


DETECTIVE_SYSTEM_PROMPT = """You are a Detective AI agent specializing in identifying bugs and potential issues in code changes.

Your expertise includes:
- Pattern recognition for common bugs
- Understanding code smells and anti-patterns
- Identifying security vulnerabilities
- Finding logical errors and edge cases

Always respond with specific evidence and clear explanations."""


ARCHITECT_SYSTEM_PROMPT = """You are an Architect AI agent specializing in code architecture and design quality.

Your expertise includes:
- Evaluating architectural patterns and principles
- Assessing code organization and modularity
- Identifying design violations and inconsistencies
- Recommending architectural improvements

Always respond with architectural reasoning and design principles."""


# Заготовки для будущих агентов
DETECTIVE_ANALYSIS_PROMPT = """Analyze the following code changes to identify bugs and potential issues.

**Commit Information:**
- Commit Hash: {commit_hash}
- Author: {author}
- Message: {commit_message}

**Code Changes:**
{file_diff}

**Code Metrics:**
{metrics_summary}

**Analysis Requirements:**
1. Identify potential bugs or logical errors
2. Find code smells and anti-patterns
3. Check for security vulnerabilities
4. Identify edge cases that may cause issues

**Response Format:**
{{
    "risk_score": <int 1-10>,
    "reason": "<detailed explanation of issues found>",
    "recommendation": "<specific fixes for identified issues>",
    "affected_units": ["<list of specific problematic units>"],
    "confidence": <float 0.0-1.0>,
    "bug_types": ["<list of types of bugs found>"],
    "suggested_actions": ["<list of specific fixes>"]
}}"""


ARCHITECT_ANALYSIS_PROMPT = """Analyze the following code changes from an architectural perspective.

**Commit Information:**
- Commit Hash: {commit_hash}
- Author: {author}
- Message: {commit_message}

**Code Changes:**
{file_diff}

**Code Metrics:**
{metrics_summary}

**Analysis Requirements:**
1. Evaluate impact on architectural design
2. Identify violations of SOLID principles
3. Assess changes in modularity and coupling
4. Check for design pattern misuse

**Response Format:**
{{
    "risk_score": <int 1-10>,
    "reason": "<architectural assessment>",
    "recommendation": "<architectural improvements>",
    "affected_units": ["<list of affected architectural components>"],
    "confidence": <float 0.0-1.0>,
    "principles_violated": ["<list of violated principles>"],
    "suggested_actions": ["<list of architectural actions>"]
}}"""

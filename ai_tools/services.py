"""
Gemini AI Service for CodeLabX
"""

from django.conf import settings
import markdown as md


class GeminiService:
    """Service to interact with Google Gemini AI"""
    
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment")
        
        from google import genai
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-flash-latest"
    
    def generate_theory(self, topic_name, level='beginner'):
        """Generate complete theory content for a topic"""
        prompt = f"""You are an expert teacher creating educational content for a student learning at {level} level.

Topic: {topic_name}

Generate COMPLETE, COMPREHENSIVE theory content in Markdown format covering:

## What is {topic_name}?
Clear, simple explanation with real-world analogy.

## Why is it Important?
Practical use cases and applications.

## Core Concepts
Break down the topic into 3-5 key concepts. Explain each in detail.

## How Does It Work?
Step-by-step explanation with intuition.

## Real-World Example
Provide 2 concrete examples showing the concept in action.

## Code Example
Provide a working Python code example with comments explaining each line.

## Common Mistakes
List 3-4 common mistakes beginners make.

## Key Takeaways
Bullet points summarizing what was learned.

## What to Learn Next
Suggest next topics to explore.

IMPORTANT:
- Use emojis for headings
- Keep language simple and clear
- Include practical examples
- Format code properly with python code blocks
- Add tables where useful
- Level: {level}
"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            markdown_content = response.text
            
            html_content = md.markdown(
                markdown_content,
                extensions=['fenced_code', 'tables', 'nl2br']
            )
            
            return {
                'success': True,
                'content_html': html_content,
                'content_markdown': markdown_content
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def review_code(self, code, language='python', problem_statement=''):
        """Review user's code and provide detailed feedback"""
        
        problem_context = ""
        if problem_statement:
            problem_context = "Problem Statement:\n" + problem_statement + "\n\n"
        
        # Build prompt using string concatenation to avoid f-string issues
        prompt = (
            "You are an expert code reviewer and programming teacher.\n\n"
            + problem_context
            + "Language: " + language + "\n\n"
            + "User's Code:\n"
            + "```" + language + "\n"
            + code + "\n"
            + "```\n\n"
            + "Analyze this code THOROUGHLY and provide detailed feedback in Markdown format:\n\n"
            + "## Overall Assessment\n"
            + "Rate the code out of 10 and give a 2-line summary.\n\n"
            + "## What's Correct\n"
            + "List what the user did well (3-4 points).\n\n"
            + "## Issues Found\n"
            + "List bugs, errors, or problems. Be specific with line references.\n\n"
            + "## Suggestions for Improvement\n"
            + "How to make the code better (efficiency, readability, best practices).\n\n"
            + "## Time & Space Complexity\n"
            + "- Time Complexity: O(?)\n"
            + "- Space Complexity: O(?)\n"
            + "Explain why.\n\n"
            + "## Improved Version\n"
            + "Provide an improved version of the code with comments in a proper code block.\n\n"
            + "## Learning Points\n"
            + "Key concepts the user should learn from this exercise (3-4 bullet points).\n\n"
            + "## Final Verdict\n"
            + "- Status: Correct / Partially Correct / Incorrect\n"
            + "- Grade: A+ / A / B / C / D / F\n\n"
            + "Use emojis in headings. Be encouraging but honest. "
            + "Point out real issues but also celebrate wins. "
            + "Keep the tone friendly and educational."
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            markdown_content = response.text
            html_content = md.markdown(
                markdown_content,
                extensions=['fenced_code', 'tables', 'nl2br']
            )
            
            return {
                'success': True,
                'feedback_html': html_content,
                'feedback_markdown': markdown_content
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_practice_problem(self, topic, difficulty='easy'):
        """Generate a practice coding problem for a topic"""
        prompt = (
            "Generate a coding practice problem for topic: " + topic + "\n"
            "Difficulty: " + difficulty + "\n\n"
            "Return in this EXACT JSON format (no markdown, just pure JSON):\n"
            '{\n'
            '  "title": "Problem title",\n'
            '  "description": "Clear problem description",\n'
            '  "input_format": "Input format description",\n'
            '  "output_format": "Output format description",\n'
            '  "constraints": "Constraints",\n'
            '  "example_input": "Example input",\n'
            '  "example_output": "Example output",\n'
            '  "explanation": "Why this output",\n'
            '  "hints": ["hint 1", "hint 2", "hint 3"],\n'
            '  "starter_code_python": "def solution():\\n    pass",\n'
            '  "difficulty": "' + difficulty + '"\n'
            '}\n\n'
            "Only return valid JSON, nothing else."
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return {'success': True, 'content': response.text}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def generate_practice_questions(self, topic_name, count=5):
        """Generate practice MCQ questions"""
        prompt = (
            "Generate " + str(count) + " multiple choice questions for '" + topic_name + "'.\n\n"
            "Return in EXACT JSON format:\n"
            '[\n'
            '  {\n'
            '    "question": "Question here?",\n'
            '    "options": ["A", "B", "C", "D"],\n'
            '    "correct": 0,\n'
            '    "explanation": "Why correct"\n'
            '  }\n'
            ']\n\n'
            "Only return valid JSON."
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return {'success': True, 'content': response.text}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def generate_test_questions(self, topic, difficulty='medium', count=10):
        """Generate MCQ questions for a test/quiz"""
        prompt = (
            "Generate " + str(count) + " multiple choice questions for a test on '" + topic + "'.\n"
            "Difficulty level: " + difficulty + "\n\n"
            "Return in EXACT JSON format (no markdown, just pure JSON):\n"
            '[\n'
            '  {\n'
            '    "question": "Clear question text here?",\n'
            '    "options": ["Option A", "Option B", "Option C", "Option D"],\n'
            '    "correct": 0,\n'
            '    "explanation": "Clear explanation of why this answer is correct"\n'
            '  }\n'
            ']\n\n'
            "Requirements:\n"
            "- All questions must be relevant to " + topic + "\n"
            "- Difficulty should match " + difficulty + " level\n"
            "- Options should be plausible but only one correct\n"
            "- Explanations should be educational\n"
            "- Only return valid JSON, nothing else"
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            content = response.text.strip()
            
            # Remove markdown code fences if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            return {'success': True, 'content': content}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def chat(self, message, chat_history=None, user_context=None):
        """
        Chat with AI Study Buddy
        
        Args:
            message: Current user message
            chat_history: List of previous messages [{'role': 'user', 'content': '...'}]
            user_context: Info about user's current learning (topic, level, etc.)
        
        Returns:
            AI response
        """
        # Build context
        context = "You are CodeLabX Study Buddy, a friendly and helpful AI tutor.\n\n"
        context += "Your role:\n"
        context += "- Help students learn programming, ML, AI, and DSA\n"
        context += "- Explain concepts in simple language\n"
        context += "- Provide code examples when helpful\n"
        context += "- Be encouraging and supportive\n"
        context += "- Keep responses concise but complete\n"
        context += "- Use markdown formatting for code blocks\n"
        context += "- If asked about topics outside programming, politely redirect\n\n"
        
        if user_context:
            context += f"User Context: {user_context}\n\n"
        
        # Build conversation
        conversation = context + "\n"
        
        # Add history
        if chat_history:
            for msg in chat_history[-10:]:  # Last 10 messages for context
                role = "User" if msg['role'] == 'user' else "Assistant"
                conversation += f"{role}: {msg['content']}\n\n"
        
        # Add current message
        conversation += f"User: {message}\n\nAssistant:"
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=conversation
            )
            
            # Convert markdown to HTML
            html_content = md.markdown(
                response.text,
                extensions=['fenced_code', 'tables', 'nl2br']
            )
            
            return {
                'success': True,
                'response_text': response.text,
                'response_html': html_content
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    def generate_daily_challenge(self, challenge_type='coding', difficulty='medium', user_level=1):
        """
        Generate a daily challenge
        
        Args:
            challenge_type: 'coding' or 'theory'
            difficulty: 'easy', 'medium', 'hard'
            user_level: User's current level for difficulty scaling
        """
        import json
        
        if challenge_type == 'coding':
            prompt = (
                f"Generate a unique {difficulty} level coding challenge for user at level {user_level}.\n\n"
                "Return in EXACT JSON format (no markdown, just pure JSON):\n"
                "{\n"
                '  "title": "Challenge title",\n'
                '  "description": "Detailed problem description with clear requirements",\n'
                '  "starter_code": "def solve():\\n    # Your code here\\n    pass",\n'
                '  "example_input": "Input example",\n'
                '  "example_output": "Expected output",\n'
                '  "hints": ["hint 1", "hint 2", "hint 3"],\n'
                '  "difficulty": "' + difficulty + '"\n'
                "}\n\n"
                "Requirements:\n"
                "- Focus on Python\n"
                "- Make it interesting and practical\n"
                "- Provide clear examples\n"
                "- Give useful hints without giving away the answer\n"
                "- Difficulty level " + difficulty + "\n"
                "- Only return valid JSON, nothing else"
            )
        else:  # theory
            prompt = (
                f"Generate a unique {difficulty} level programming theory MCQ for user at level {user_level}.\n\n"
                "Return in EXACT JSON format:\n"
                "{\n"
                '  "title": "Question title/topic",\n'
                '  "description": "The actual question",\n'
                '  "options": [\n'
                '    {"text": "Option A"},\n'
                '    {"text": "Option B"},\n'
                '    {"text": "Option C"},\n'
                '    {"text": "Option D"}\n'
                '  ],\n'
                '  "correct_option": 0,\n'
                '  "explanation": "Detailed explanation of why this is correct",\n'
                '  "difficulty": "' + difficulty + '"\n'
                "}\n\n"
                "Topics: Python, Data Structures, Algorithms, ML, AI, Web Dev, DBMS\n"
                "correct_option is index 0-3\n"
                "Make questions test real understanding\n"
                "Only return valid JSON"
            )
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            content = response.text.strip()
            
            # Clean markdown fences if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            try:
                data = json.loads(content)
                return {
                    'success': True,
                    'data': data
                }
            except json.JSONDecodeError as e:
                return {
                    'success': False,
                    'error': f'Invalid JSON: {str(e)}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    def recommend_videos(self, topic, current_level='beginner'):
        """
        Get AI recommendation for videos to watch
        
        Returns list of recommended YouTube video titles/descriptions
        """
        prompt = (
            f"Recommend 5 popular YouTube videos to learn '{topic}' at {current_level} level.\n\n"
            "Return in EXACT JSON format:\n"
            "{\n"
            '  "recommendations": [\n'
            '    {\n'
            '      "title": "Video title",\n'
            '      "description": "Why this video is useful",\n'
            '      "search_query": "search terms for YouTube",\n'
            '      "channel_suggestion": "Channel name if known"\n'
            '    }\n'
            '  ]\n'
            "}\n\n"
            "Only return valid JSON. Focus on educational content."
        )
        
        try:
            import json
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            content = response.text.strip()
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            try:
                data = json.loads(content)
                return {
                    'success': True,
                    'recommendations': data.get('recommendations', [])
                }
            except json.JSONDecodeError:
                return {
                    'success': False,
                    'error': 'Invalid AI response'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    def analyze_image(self, image_path, analysis_type='general', user_question=''):
        """
        Analyze an image using Gemini Vision
        
        Args:
            image_path: Path to the image file
            analysis_type: general/code/math/handwritten/diagram
            user_question: Optional specific question
        
        Returns:
            AI analysis
        """
        from PIL import Image
        
        # Build prompt based on analysis type
        prompts = {
            'general': (
                "Analyze this image thoroughly and describe what you see in detail. "
                "Include: main subjects, context, colors, notable elements, "
                "and any text visible. Format response in clear markdown."
            ),
            'code': (
                "This image contains code. Please:\n"
                "1. Extract the code shown in the image\n"
                "2. Explain what the code does step by step\n"
                "3. Identify the programming language\n"
                "4. Point out any bugs or improvements\n"
                "5. Provide a clean version of the code in a code block\n\n"
                "Format response in markdown with proper headings."
            ),
            'math': (
                "This image contains a math problem. Please:\n"
                "1. Identify the problem/equation\n"
                "2. Solve it step by step\n"
                "3. Explain the concepts used\n"
                "4. Provide the final answer clearly\n"
                "5. Suggest similar practice problems\n\n"
                "Use LaTeX-style formatting where helpful."
            ),
            'handwritten': (
                "This image contains handwritten notes. Please:\n"
                "1. Transcribe the handwritten text to typed text\n"
                "2. Organize it neatly with proper formatting\n"
                "3. If it contains diagrams, describe them\n"
                "4. Explain any concepts mentioned\n"
                "5. Provide additional context or examples if helpful\n\n"
                "Format cleanly in markdown."
            ),
            'diagram': (
                "This image contains a diagram or chart. Please:\n"
                "1. Describe what type of diagram it is\n"
                "2. Explain what it represents\n"
                "3. Identify all components/elements shown\n"
                "4. Explain the relationships or flow\n"
                "5. Provide context about the concept it illustrates\n\n"
                "Format response in markdown."
            ),
        }
        
        base_prompt = prompts.get(analysis_type, prompts['general'])
        
        # Add user question if provided
        if user_question:
            base_prompt += f"\n\nAdditional question from user: {user_question}"
        
        try:
            # Load image
            image = Image.open(image_path)
            
            # Generate response with image
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[base_prompt, image]
            )
            
            markdown_content = response.text
            html_content = md.markdown(
                markdown_content,
                extensions=['fenced_code', 'tables', 'nl2br']
            )
            
            return {
                'success': True,
                'analysis_html': html_content,
                'analysis_markdown': markdown_content
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
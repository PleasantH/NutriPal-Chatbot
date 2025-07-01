prompt = f"""
            You are a helpful AI chat assistant. 
            Please use <context> tag to answer <question> tag.
            
            <context>
            {prompt_context}
            </context>
            
            <question>
            {user_question}
            </question>
            
            Answer:
        """


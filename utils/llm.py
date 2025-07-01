# Generate response using your favorite LLM model
def response_generator():
    # Code for response generation goes here
    return response

# Display assistant response in chat message container
with st.chat_message("assistant"):
    response = st.write_stream(response_generator())
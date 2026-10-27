"use strict";

// Extracted page behavior: ai_tools-chat_sessions.js
document.querySelectorAll('.session-button').forEach(button=>button.addEventListener('click',async()=>{const target=document.getElementById('conversation');target.textContent='Loading…';try{const response=await fetch(`/ai-tools/chat/session/${button.dataset.sessionId}/`);const data=await response.json();target.textContent='';if(!response.ok||!data.success){target.textContent=data.error||'Unable to load conversation.';return;}data.messages.forEach(item=>{const box=document.createElement('div');box.className=`message ${item.role}`;if(item.role==='assistant'){box.innerHTML=item.content_html;}else{box.textContent=item.content;}target.appendChild(box);});}catch(error){target.textContent='Unable to load conversation.';}}));

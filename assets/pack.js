(() => {
  "use strict";
  const main = document.querySelector("#pack-main");
  const file = new URLSearchParams(window.location.search).get("file") || "";
  const allowed = /^data\/drafts\/[A-Za-z0-9_-]+\.md$/;
  const text = (tag, value, className = "") => { const node=document.createElement(tag); node.textContent=value; if(className)node.className=className; return node; };

  function inline(value) {
    const fragment = document.createDocumentFragment();
    const pattern = /(https?:\/\/[^\s)]+|`[^`]+`|\*\*[^*]+\*\*)/g;
    let last=0; let match;
    while ((match=pattern.exec(value)) !== null) {
      if (match.index>last) fragment.appendChild(document.createTextNode(value.slice(last,match.index)));
      const token=match[0];
      if (token.startsWith("http")) { const a=document.createElement("a"); a.href=token; a.target="_blank"; a.rel="noopener noreferrer"; a.textContent=token; fragment.appendChild(a); }
      else if (token.startsWith("`")) fragment.appendChild(text("code",token.slice(1,-1)));
      else { const strong=text("strong",token.slice(2,-2)); fragment.appendChild(strong); }
      last=match.index+token.length;
    }
    if(last<value.length)fragment.appendChild(document.createTextNode(value.slice(last)));
    return fragment;
  }

  function markdownFragment(markdown) {
    const fragment=document.createDocumentFragment(); const lines=markdown.replace(/\r/g,"").split("\n"); let list=null; let pre=null;
    const closeList=()=>{if(list){fragment.appendChild(list);list=null;}};
    const closePre=()=>{if(pre){fragment.appendChild(pre);pre=null;}};
    for(const line of lines){
      if(line.startsWith("```")){closeList(); if(pre){closePre();}else pre=document.createElement("pre"); continue;}
      if(pre){pre.appendChild(document.createTextNode(line+"\n")); continue;}
      if(/^\s*$/.test(line)){closeList(); continue;}
      const heading=line.match(/^(#{1,3})\s+(.+)$/); if(heading){closeList(); const level=Math.min(3,heading[1].length); const node=text(`h${level}`,heading[2]); node.replaceChildren(inline(heading[2])); fragment.appendChild(node); continue;}
      const bullet=line.match(/^\s*[-*]\s+(?:\[([ xX])\]\s+)?(.+)$/); if(bullet){if(!list)list=document.createElement("ul"); const li=document.createElement("li"); li.appendChild(inline(`${bullet[1] ? (bullet[1].toLowerCase()==="x" ? "☑ " : "☐ ") : ""}${bullet[2]}`)); list.appendChild(li); continue;}
      if(line.startsWith(">")){closeList(); const quote=text("blockquote",line.replace(/^>\s?/,"")); quote.replaceChildren(inline(line.replace(/^>\s?/,""))); fragment.appendChild(quote); continue;}
      closeList(); const p=text("p"); p.appendChild(inline(line)); fragment.appendChild(p);
    }
    closeList(); closePre(); return fragment;
  }

  function sections(markdown) {
    const result=[]; let current=null;
    for(const line of markdown.replace(/\r/g,"").split("\n")){
      const heading=line.match(/^(#{1,3})\s+(.+)$/);
      if(heading){ if(current) result.push(current); current={level:heading[1].length,title:heading[2],body:[]}; }
      else if(current) current.body.push(line);
    }
    if(current) result.push(current);
    return result;
  }

  function copyReady(value) {
    return value.replace(/\r/g,"").trim().replace(/^```[^\n]*\n/, "").replace(/\n```\s*$/, "").trim();
  }

  async function copyText(value, button) {
    try {
      await navigator.clipboard.writeText(copyReady(value));
      const old=button.textContent; button.textContent="コピーしました"; button.classList.add("copy-ok");
      setTimeout(()=>{button.textContent=old; button.classList.remove("copy-ok");},1800);
    } catch (_) { button.textContent="コピー失敗"; }
  }

  function render(markdown) {
    const parts=sections(markdown); const wrapper=document.createDocumentFragment();
    const toolbar=text("div","発信に使う部分を選んでコピーできます。","copy-toolbar");
    const all=document.createElement("button"); all.type="button"; all.className="copy-button"; all.textContent="発信用テキストを全部コピー";
    all.addEventListener("click",()=>copyText(parts.map(part=>part.body.join("\n")).join("\n\n"),all)); toolbar.appendChild(all); wrapper.appendChild(toolbar);
    for(const part of parts){
      const box=document.createElement("section"); box.className="copy-section";
      const bar=document.createElement("div"); bar.className="copy-section-head";
      const heading=text(`h${Math.min(3,part.level)}`,part.title); bar.appendChild(heading);
      const button=document.createElement("button"); button.type="button"; button.className="copy-button"; button.textContent="この部分をコピー";
      button.addEventListener("click",()=>copyText(part.body.join("\n"),button)); bar.appendChild(button); box.appendChild(bar);
      box.appendChild(markdownFragment(part.body.join("\n"))); wrapper.appendChild(box);
    }
    main.replaceChildren(wrapper);
  }

  async function load(){
    if(!allowed.test(file)){main.replaceChildren(text("div","発信用パックの指定が不正です。ダッシュボードへ戻ってください。","pack-error"));return;}
    try{const response=await fetch(`${file}?v=${Date.now()}`,{cache:"no-store"}); if(!response.ok)throw new Error(String(response.status)); const markdown=await response.text(); render(markdown);}
    catch(error){console.error("pack load failed",error);main.replaceChildren(text("div","発信用パックを取得できませんでした。少し時間を置いて再度お試しください。","pack-error"));}
  }
  load();
})();

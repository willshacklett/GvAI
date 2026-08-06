(function(){let e=document.createElement(`link`).relList;if(e&&e.supports&&e.supports(`modulepreload`))return;for(let e of document.querySelectorAll(`link[rel="modulepreload"]`))n(e);new MutationObserver(e=>{for(let t of e)if(t.type===`childList`)for(let e of t.addedNodes)e.tagName===`LINK`&&e.rel===`modulepreload`&&n(e)}).observe(document,{childList:!0,subtree:!0});function t(e){let t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),t.credentials=e.crossOrigin===`use-credentials`?`include`:e.crossOrigin===`anonymous`?`omit`:`same-origin`,t}function n(e){if(e.ep)return;e.ep=!0;let n=t(e);fetch(e.href,n)}})(),((e,t)=>()=>(t||(e((t={exports:{}}).exports,t),e=null),t.exports))((()=>{var e=document.getElementById(`avatar-root`);document.documentElement.style.cssText=`
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
`,document.body.style.cssText=`
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
`,e.innerHTML=`
  <svg
    id="carlSvg"
    viewBox="0 0 320 320"
    xmlns="http://www.w3.org/2000/svg"
    role="img"
    aria-label="Carl live avatar"
  >
    <defs>
      <radialGradient id="stageBg" cx="50%" cy="42%" r="65%">
        <stop offset="0%" stop-color="#17366c"/>
        <stop offset="58%" stop-color="#091a38"/>
        <stop offset="100%" stop-color="#030a17"/>
      </radialGradient>

      <linearGradient id="shell" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#ffffff"/>
        <stop offset="35%" stop-color="#dce5f1"/>
        <stop offset="68%" stop-color="#7d8ca6"/>
        <stop offset="100%" stop-color="#39465e"/>
      </linearGradient>

      <linearGradient id="torso" x1="20%" y1="0%" x2="80%" y2="100%">
        <stop offset="0%" stop-color="#f7f9fc"/>
        <stop offset="55%" stop-color="#a8b5c9"/>
        <stop offset="100%" stop-color="#40506a"/>
      </linearGradient>

      <radialGradient id="screen" cx="50%" cy="35%" r="72%">
        <stop offset="0%" stop-color="#102b55"/>
        <stop offset="50%" stop-color="#06162f"/>
        <stop offset="100%" stop-color="#01050d"/>
      </radialGradient>

      <filter id="blueGlow" x="-100%" y="-100%" width="300%" height="300%">
        <feGaussianBlur stdDeviation="5" result="blur"/>
        <feMerge>
          <feMergeNode in="blur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>

      <filter id="softShadow" x="-50%" y="-50%" width="200%" height="200%">
        <feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000814" flood-opacity=".55"/>
      </filter>
    </defs>

    <circle cx="160" cy="160" r="154" fill="url(#stageBg)"/>
    <circle
      id="statusRing"
      cx="160"
      cy="160"
      r="148"
      fill="none"
      stroke="#347cff"
      stroke-width="3"
      opacity=".95"
      filter="url(#blueGlow)"
    />

    <g id="carlBody" filter="url(#softShadow)">
      <path
        id="shoulders"
        d="M79 282 C84 232 115 214 160 214 C205 214 236 232 241 282 Z"
        fill="url(#torso)"
        stroke="#dce6f5"
        stroke-opacity=".35"
        stroke-width="2"
      />

      <rect
        x="138"
        y="198"
        width="44"
        height="35"
        rx="14"
        fill="#18253d"
      />

      <circle
        id="core"
        cx="160"
        cy="253"
        r="15"
        fill="#2797ff"
        stroke="#90ccff"
        stroke-width="4"
        filter="url(#blueGlow)"
      />

      <g id="head">
        <rect
          x="58"
          y="75"
          width="28"
          height="96"
          rx="14"
          fill="url(#shell)"
          stroke="#4a9cff"
          stroke-width="3"
        />

        <rect
          x="234"
          y="75"
          width="28"
          height="96"
          rx="14"
          fill="url(#shell)"
          stroke="#4a9cff"
          stroke-width="3"
        />

        <rect
          x="66"
          y="90"
          width="10"
          height="63"
          rx="5"
          fill="#1f91ff"
          filter="url(#blueGlow)"
        />

        <rect
          x="244"
          y="90"
          width="10"
          height="63"
          rx="5"
          fill="#1f91ff"
          filter="url(#blueGlow)"
        />

        <rect
          x="76"
          y="38"
          width="168"
          height="174"
          rx="72"
          fill="url(#shell)"
          stroke="#ffffff"
          stroke-opacity=".45"
          stroke-width="2"
        />

        <rect
          id="faceScreen"
          x="91"
          y="66"
          width="138"
          height="122"
          rx="51"
          fill="url(#screen)"
          stroke="#4d8ee8"
          stroke-opacity=".55"
          stroke-width="2"
        />

        <path
          d="M108 81 C130 64 190 64 212 81"
          fill="none"
          stroke="#ffffff"
          stroke-opacity=".14"
          stroke-width="8"
          stroke-linecap="round"
        />

        <g id="eyes" filter="url(#blueGlow)">
          <ellipse
            id="leftEye"
            cx="132"
            cy="118"
            rx="12"
            ry="16"
            fill="none"
            stroke="#38a9ff"
            stroke-width="6"
          />

          <ellipse
            id="rightEye"
            cx="188"
            cy="118"
            rx="12"
            ry="16"
            fill="none"
            stroke="#38a9ff"
            stroke-width="6"
          />
        </g>

        <path
          id="mouth"
          d="M137 151 Q160 169 183 151"
          fill="none"
          stroke="#38a9ff"
          stroke-width="6"
          stroke-linecap="round"
          filter="url(#blueGlow)"
        />

        <path
          id="leftBrow"
          d="M119 94 Q132 87 145 94"
          fill="none"
          stroke="#38a9ff"
          stroke-width="4"
          stroke-linecap="round"
          opacity="0"
        />

        <path
          id="rightBrow"
          d="M175 94 Q188 87 201 94"
          fill="none"
          stroke="#38a9ff"
          stroke-width="4"
          stroke-linecap="round"
          opacity="0"
        />
      </g>
    </g>
  </svg>
`;var t=document.getElementById(`head`),n=document.getElementById(`carlBody`),r=document.getElementById(`leftEye`),i=document.getElementById(`rightEye`),a=document.getElementById(`mouth`),o=document.getElementById(`leftBrow`),s=document.getElementById(`rightBrow`),c=document.getElementById(`core`),l=document.getElementById(`statusRing`),u=`ready`,d=0,f=performance.now()+1800,p=performance.now(),m=0,h=[`ready`,`listening`,`thinking`,`speaking`,`happy`,`concerned`];function g(e){u=h.includes(e)?e:`ready`}function _(){r.setAttribute(`cx`,`132`),r.setAttribute(`cy`,`118`),r.setAttribute(`rx`,`12`),r.setAttribute(`ry`,`16`),i.setAttribute(`cx`,`188`),i.setAttribute(`cy`,`118`),i.setAttribute(`rx`,`12`),i.setAttribute(`ry`,`16`)}function v(e,n){let f=e<d;if(_(),o.setAttribute(`opacity`,`0`),s.setAttribute(`opacity`,`0`),r.style.transformOrigin=`132px 118px`,i.style.transformOrigin=`188px 118px`,r.style.transform=f?`scaleY(0.08)`:`scaleY(1)`,i.style.transform=f?`scaleY(0.08)`:`scaleY(1)`,l.setAttribute(`stroke`,`#347cff`),c.setAttribute(`fill`,`#2797ff`),u===`listening`)t.style.transformOrigin=`160px 170px`,t.style.transform=`rotate(-4deg)`,l.setAttribute(`stroke`,`#45c8ff`),c.setAttribute(`fill`,`#45c8ff`),a.setAttribute(`d`,`M140 153 Q160 163 180 153`);else if(u===`thinking`)t.style.transformOrigin=`160px 170px`,t.style.transform=`rotate(3deg) translateY(-2px)`,r.setAttribute(`cy`,`112`),i.setAttribute(`cy`,`112`),o.setAttribute(`opacity`,`1`),s.setAttribute(`opacity`,`1`),a.setAttribute(`d`,`M145 156 Q160 153 175 156`),l.setAttribute(`stroke`,`#7b8dff`);else if(u===`speaking`){m+=n*.012;let e=Math.abs(Math.sin(m)),r=17+e*8,i=150-e*2,o=159+e*15;a.setAttribute(`d`,`M${160-r} ${i}
       Q160 ${o}
       ${160+r} ${i}`);let s=14+e*4;c.setAttribute(`r`,String(s)),t.style.transformOrigin=`160px 170px`,t.style.transform=`rotate(${Math.sin(m*.35)*1.8}deg)`}else u===`happy`?(r.setAttribute(`ry`,`7`),i.setAttribute(`ry`,`7`),r.setAttribute(`cy`,`121`),i.setAttribute(`cy`,`121`),a.setAttribute(`d`,`M132 145 Q160 181 188 145`),c.setAttribute(`fill`,`#45e49b`),l.setAttribute(`stroke`,`#45e49b`)):u===`concerned`?(o.setAttribute(`opacity`,`1`),s.setAttribute(`opacity`,`1`),o.setAttribute(`d`,`M119 99 Q132 91 145 101`),s.setAttribute(`d`,`M175 101 Q188 91 201 99`),a.setAttribute(`d`,`M138 166 Q160 145 182 166`),c.setAttribute(`fill`,`#ffb347`),l.setAttribute(`stroke`,`#ffb347`),t.style.transformOrigin=`160px 170px`,t.style.transform=`rotate(3deg)`):(t.style.transformOrigin=`160px 170px`,t.style.transform=`rotate(${Math.sin(e*45e-5)*.8}deg)`,a.setAttribute(`d`,`M137 151 Q160 169 183 151`))}window.addEventListener(`message`,e=>{e.data?.type===`carl-state`&&g(e.data.state)}),e.addEventListener(`click`,()=>{g(h[(h.indexOf(u)+1)%h.length])});function y(e){let t=e-p;p=e,e>=f&&(d=e+135,f=e+2600+Math.random()*3200);let r=Math.sin(e*.0014)*1.7;n.style.transformOrigin=`160px 270px`,n.style.transform=`translateY(${r}px)`,l.setAttribute(`opacity`,String(.78+Math.sin(e*.0022)*.14)),v(e,t),requestAnimationFrame(y)}requestAnimationFrame(y)}))();
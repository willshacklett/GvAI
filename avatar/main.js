const root = document.getElementById("avatar-root");

document.documentElement.style.cssText = `
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
`;

document.body.style.cssText = `
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
`;

root.innerHTML = `
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
`;

const head = document.getElementById("head");
const body = document.getElementById("carlBody");
const leftEye = document.getElementById("leftEye");
const rightEye = document.getElementById("rightEye");
const mouth = document.getElementById("mouth");
const leftBrow = document.getElementById("leftBrow");
const rightBrow = document.getElementById("rightBrow");
const core = document.getElementById("core");
const ring = document.getElementById("statusRing");

let state = "ready";
let blinkUntil = 0;
let nextBlink = performance.now() + 1800;
let lastTime = performance.now();
let speechPhase = 0;

const states = [
  "ready",
  "listening",
  "thinking",
  "speaking",
  "happy",
  "concerned",
];

function setState(nextState) {
  state = states.includes(nextState) ? nextState : "ready";
}

function eyeShape(type) {
  switch (type) {
    case "happy":
      leftEye.setAttribute("d", "M119 121 Q132 106 145 121");
      rightEye.setAttribute("d", "M175 121 Q188 106 201 121");
      break;
  }
}

function restoreEllipseEyes() {
  leftEye.setAttribute("cx", "132");
  leftEye.setAttribute("cy", "118");
  leftEye.setAttribute("rx", "12");
  leftEye.setAttribute("ry", "16");
  rightEye.setAttribute("cx", "188");
  rightEye.setAttribute("cy", "118");
  rightEye.setAttribute("rx", "12");
  rightEye.setAttribute("ry", "16");
}

function applyExpression(now, delta) {
  const blinkActive = now < blinkUntil;

  restoreEllipseEyes();

  leftBrow.setAttribute("opacity", "0");
  rightBrow.setAttribute("opacity", "0");

  leftEye.style.transformOrigin = "132px 118px";
  rightEye.style.transformOrigin = "188px 118px";

  leftEye.style.transform = blinkActive ? "scaleY(0.08)" : "scaleY(1)";
  rightEye.style.transform = blinkActive ? "scaleY(0.08)" : "scaleY(1)";

  ring.setAttribute("stroke", "#347cff");
  core.setAttribute("fill", "#2797ff");

  if (state === "listening") {
    head.style.transformOrigin = "160px 170px";
    head.style.transform = "rotate(-4deg)";
    ring.setAttribute("stroke", "#45c8ff");
    core.setAttribute("fill", "#45c8ff");
    mouth.setAttribute("d", "M140 153 Q160 163 180 153");
  } else if (state === "thinking") {
    head.style.transformOrigin = "160px 170px";
    head.style.transform = "rotate(3deg) translateY(-2px)";

    leftEye.setAttribute("cy", "112");
    rightEye.setAttribute("cy", "112");

    leftBrow.setAttribute("opacity", "1");
    rightBrow.setAttribute("opacity", "1");

    mouth.setAttribute("d", "M145 156 Q160 153 175 156");
    ring.setAttribute("stroke", "#7b8dff");
  } else if (state === "speaking") {
    speechPhase += delta * 0.012;

    const open = Math.abs(Math.sin(speechPhase));
    const mouthWidth = 17 + open * 8;
    const mouthTop = 150 - open * 2;
    const mouthBottom = 159 + open * 15;

    mouth.setAttribute(
      "d",
      `M${160 - mouthWidth} ${mouthTop}
       Q160 ${mouthBottom}
       ${160 + mouthWidth} ${mouthTop}`
    );

    const pulse = 14 + open * 4;
    core.setAttribute("r", String(pulse));

    head.style.transformOrigin = "160px 170px";
    head.style.transform =
      `rotate(${Math.sin(speechPhase * 0.35) * 1.8}deg)`;
  } else if (state === "happy") {
    leftEye.setAttribute("ry", "7");
    rightEye.setAttribute("ry", "7");

    leftEye.setAttribute("cy", "121");
    rightEye.setAttribute("cy", "121");

    mouth.setAttribute("d", "M132 145 Q160 181 188 145");

    core.setAttribute("fill", "#45e49b");
    ring.setAttribute("stroke", "#45e49b");
  } else if (state === "concerned") {
    leftBrow.setAttribute("opacity", "1");
    rightBrow.setAttribute("opacity", "1");

    leftBrow.setAttribute("d", "M119 99 Q132 91 145 101");
    rightBrow.setAttribute("d", "M175 101 Q188 91 201 99");

    mouth.setAttribute("d", "M138 166 Q160 145 182 166");

    core.setAttribute("fill", "#ffb347");
    ring.setAttribute("stroke", "#ffb347");

    head.style.transformOrigin = "160px 170px";
    head.style.transform = "rotate(3deg)";
  } else {
    head.style.transformOrigin = "160px 170px";
    head.style.transform =
      `rotate(${Math.sin(now * 0.00045) * 0.8}deg)`;

    mouth.setAttribute("d", "M137 151 Q160 169 183 151");
  }
}

window.addEventListener("message", (event) => {
  if (event.data?.type === "carl-state") {
    setState(event.data.state);
  }
});

root.addEventListener("click", () => {
  const index = states.indexOf(state);
  setState(states[(index + 1) % states.length]);
});

function animate(now) {
  const delta = now - lastTime;
  lastTime = now;

  if (now >= nextBlink) {
    blinkUntil = now + 135;
    nextBlink = now + 2600 + Math.random() * 3200;
  }

  const breathing = Math.sin(now * 0.0014) * 1.7;

  body.style.transformOrigin = "160px 270px";
  body.style.transform = `translateY(${breathing}px)`;

  ring.setAttribute(
    "opacity",
    String(0.78 + Math.sin(now * 0.0022) * 0.14)
  );

  applyExpression(now, delta);

  requestAnimationFrame(animate);
}

requestAnimationFrame(animate);

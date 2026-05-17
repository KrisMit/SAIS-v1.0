<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Biometric Art Experience</title>
    <style>
        :root { --primary-red: #ff3e3e; }
        
        body { 
            background: #000; color: #fff; font-family: 'Helvetica Neue', Arial, sans-serif; 
            margin: 0; overflow: hidden; display: flex; flex-direction: column;
            align-items: center; justify-content: center; height: 100vh;
        }

        /* Heartbeat Flash Effect */
        #heart-bg {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: radial-gradient(circle, rgba(255, 62, 62, 0.15) 0%, rgba(0,0,0,0) 70%);
            opacity: 0; pointer-events: none; z-index: 1;
        }

        #container { position: relative; width: 180px; height: 180px; z-index: 2; }
        
        canvas { 
            border-radius: 50%; border: 2px solid rgba(255,255,255,0.2); 
            width: 100%; filter: grayscale(0.5) contrast(1.2);
        }

        #bpm-display { 
            font-size: 3.5rem; font-weight: 200; margin: 20px 0; 
            color: var(--primary-red); z-index: 2; transition: all 0.5s;
        }

        #status { 
            font-size: 0.9rem; color: #888; z-index: 2; 
            max-width: 250px; line-height: 1.4; height: 3em;
        }

        .btn { 
            background: none; color: white; border: 2px solid white; 
            padding: 15px 40px; font-size: 1rem; border-radius: 0; 
            cursor: pointer; display: none; z-index: 10; margin-top: 20px;
            letter-spacing: 2px; text-transform: uppercase; transition: 0.3s;
        }
        .btn:hover { background: white; color: black; }

        /* Instruction Overlay */
        #overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: #000; z-index: 100; display: flex; flex-direction: column;
            align-items: center; justify-content: center; text-align: center;
        }

        .finger-guide {
            width: 50px; height: 80px; border: 2px solid #fff;
            border-radius: 25px; margin-bottom: 20px; position: relative;
        }
        .finger-guide::after {
            content: ''; position: absolute; top: 10px; left: 15px;
            width: 20px; height: 40px; background: var(--primary-red);
            border-radius: 10px; animation: pulse-guide 2s infinite;
        }

        @keyframes pulse-guide { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }

        /* Animations */
        .sync-pulse { animation: sync-flash 0.4s ease-out; }
        @keyframes sync-flash { 0% { opacity: 0; } 50% { opacity: 1; } 100% { opacity: 0; } }

        .bloom { transform: scale(3); opacity: 0; filter: blur(20px); }
    </style>
</head>
<body>

    <div id="heart-bg"></div>

    <div id="overlay" onclick="startExperience()">
        <div class="finger-guide"></div>
        <h2 style="font-weight: 200;">BIO-SYNC</h2>
        <p style="padding: 0 50px; color: #ccc; font-size: 0.9rem;">
            Place your <strong>index finger</strong> firmly over the <br><strong>back camera and flash</strong>.<br><br>
            <span style="color: var(--primary-red);">Tap to begin calibration.</span>
        </p>
    </div>

    <div id="container">
        <canvas id="c" width="100" height="100"></canvas>
    </div>
    
    <div id="bpm-display">--</div>
    <div id="status">Waiting for finger...</div>
    <button id="artButton" class="btn" onclick="triggerTransition()">View Painting</button>

    <video id="v" autoplay playsinline style="display:none"></video>

    <script>
        const video = document.getElementById('v');
        const canvas = document.getElementById('c');
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        const bpmDisplay = document.getElementById('bpm-display');
        const artBtn = document.getElementById('artButton');
        const heartBg = document.getElementById('heart-bg');
        const statusText = document.getElementById('status');

        let dataPoints = [];
        let lastPeakTime = 0;
        let beatCounts = [];
        let isActive = false;

        async function startExperience() {
            document.getElementById('overlay').style.opacity = '0';
            setTimeout(() => document.getElementById('overlay').remove(), 500);
            
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { facingMode: "environment" } 
                });
                video.srcObject = stream;

                const track = stream.getVideoTracks()[0];
                const capabilities = track.getCapabilities();
                if (capabilities.torch) {
                    await track.applyConstraints({ advanced: [{ torch: true }] });
                }

                isActive = true;
                requestAnimationFrame(processFrame);
            } catch (err) {
                statusText.innerText = "Camera access denied.";
            }
        }

        function processFrame() {
            if (!isActive) return;
            ctx.drawImage(video, 0, 0, 100, 100);
            const pixels = ctx.getImageData(0, 0, 100, 100).data;
            
            let rSum = 0;
            for (let i = 0; i < pixels.length; i += 4) { rSum += pixels[i]; }
            let avgRed = rSum / (pixels.length / 4);

            // If the screen isn't red enough, the finger isn't on the camera
            if (avgRed < 150) {
                statusText.innerText = "LENS NOT COVERED";
                bpmDisplay.innerText = "--";
            } else {
                statusText.innerText = "SYNCING WITH HEARTBEAT...";
                analyzePulse(avgRed);
            }
            requestAnimationFrame(processFrame);
        }

        function analyzePulse(val) {
            const now = Date.now();
            dataPoints.push(val);
            if (dataPoints.length > 30) dataPoints.shift();

            const movingAvg = dataPoints.reduce((a, b) => a + b) / dataPoints.length;
            
            // Detection: Current frame is higher than average (the surge of blood)
            if (val > movingAvg * 1.0015 && (now - lastPeakTime) > 450) {
                const bpm = Math.round(60000 / (now - lastPeakTime));
                
                if (bpm > 45 && bpm < 160) {
                    beatCounts.push(bpm);
                    if (beatCounts.length > 8) beatCounts.shift();
                    
                    const averageBpm = Math.round(beatCounts.reduce((a, b) => a + b) / beatCounts.length);
                    bpmDisplay.innerText = averageBpm;

                    // Visual Heartbeat Sync
                    heartBg.classList.remove('sync-pulse');
                    void heartBg.offsetWidth; // Trigger reflow
                    heartBg.classList.add('sync-pulse');

                    if (beatCounts.length >= 8) {
                        statusText.innerText = "HEARTBEAT STABILIZED";
                        artBtn.style.display = "block";
                    }
                }
                lastPeakTime = now;
            }
        }

        function triggerTransition() {
            isActive = false;
            bpmDisplay.classList.add('bloom');
            statusText.style.opacity = '0';
            artBtn.style.opacity = '0';
            
            setTimeout(() => {
                // REPLACE THIS URL with Artivive WebAR Link
                window.location.href = "https://artivive.com/webar/YOUR_ARTWORK_ID";
            }, 800);
        }
    </script>
</body>
</html>
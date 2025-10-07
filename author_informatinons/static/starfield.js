
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('starfield');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    const numStars = 2000; // 降低密度
    let stars = [];
    const colors = ['#8EB9E8', '#A2CCF6', '#B9D7F8', '#D0E3FA', '#FFFFFF'];

    function initStars() {
        stars = [];
        for (let i = 0; i < numStars; i++) {
            stars.push({
                x: (Math.random() - 0.5) * canvas.width * 2,
                y: (Math.random() - 0.5) * canvas.height * 2,
                z: Math.random() * 2000,
                color: colors[Math.floor(Math.random() * colors.length)]
            });
        }
    }
    initStars();

    let speed = 0.5;

    window.addEventListener('scroll', () => {
        const scrollSpeed = window.scrollY / 100;
        speed = Math.max(0.5, Math.min(25, 0.5 + scrollSpeed));
    });

    function update() {
        for (let i = 0; i < numStars; i++) {
            stars[i].z -= speed;

            if (stars[i].z <= 0) {
                stars[i].z = 2000;
                stars[i].x = (Math.random() - 0.5) * canvas.width * 2;
                stars[i].y = (Math.random() - 0.5) * canvas.height * 2;
            }
        }
    }

    function draw() {
        ctx.fillStyle = "#0a1020";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        ctx.save();
        ctx.translate(canvas.width / 2, canvas.height / 2);

        for (let i = 0; i < numStars; i++) {
            const star = stars[i];

            const k = 256 / star.z;
            const px = star.x * k;
            const py = star.y * k;

            // 提高基础尺寸和最小亮度
            const size = (1 - star.z / 2000) * 3.5;
            const alpha = 0.2 + (1 - star.z / 2000) * 0.8;

            ctx.fillStyle = star.color;
            ctx.globalAlpha = alpha;
            ctx.shadowBlur = 7; // 减小辉光范围，使其更清晰
            ctx.shadowColor = star.color;

            ctx.beginPath();
            ctx.arc(px, py, size, 0, Math.PI * 2);
            ctx.fill();
        }
        ctx.restore();
    }

    function animate() {
        update();
        draw();
        requestAnimationFrame(animate);
    }

    animate();
});

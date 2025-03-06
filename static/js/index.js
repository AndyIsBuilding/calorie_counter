// Wait for DOM to be fully loaded before running the code
document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide icons
    lucide.createIcons();

    // Features data (you might want to move this to an API endpoint as well)
    const features = [
    {
        title: "Easy Logging",
        description: "Quickly log your meals with our intuitive interface and extensive food database.",
        icon: "utensils",
    },
    {
        title: "Detailed Analytics",
        description: "View your nutrition trends with beautiful, easy-to-understand charts and graphs.",
        icon: "bar-chart-2",
    },
    {
        title: "Goal Setting",
        description: "Set personalized calorie and protein goals, and track your progress over time.",
        icon: "zap",
    },
    {
        title: "Daily Planning",
        description: "Plan your meals in advance and stay on track with your nutrition goals.",
        icon: "calendar",
    },
    ];

    // Populate features
    const featuresGrid = document.getElementById('features-grid');
    features.forEach(feature => {
        const featureCard = document.createElement('div');
        featureCard.className = 'bg-white rounded-lg border border-gray-200 shadow-md';
        featureCard.innerHTML = `
            <div class="p-6">
                <div class="flex items-center space-x-4 mb-4">
                    <i data-lucide="${feature.icon}" class="h-10 w-10 text-primary"></i>
                    <h3 class="text-xl font-semibold">${feature.title}</h3>
                </div>
                <p class="text-muted-foreground">${feature.description}</p>
            </div>
        `;
        featuresGrid.appendChild(featureCard);
    });

    // Fetch and populate testimonials
    fetch('/api/testimonials')
        .then(response => response.json())
        .then(testimonials => {
            const testimonialsGrid = document.getElementById('testimonials-grid');
            testimonials.forEach(testimonial => {
                const testimonialCard = document.createElement('div');
                testimonialCard.className = 'bg-white rounded-lg border border-gray-200 shadow-md';
                testimonialCard.innerHTML = `
                    <div class="p-6">
                    <blockquote class="text-lg mb-4">"${testimonial.quote}"</blockquote>
                    <cite class="flex items-center space-x-4">
                        <div class="w-12 h-12 bg-primary rounded-full flex items-center justify-center text-white font-bold text-xl">
                        ${testimonial.author[0]}
                        </div>
                        <div>
                        <div class="font-semibold">${testimonial.author}</div>
                        <div class="text-sm text-muted-foreground">${testimonial.role}</div>
                        </div>
                    </cite>
                    </div>
                `;
                testimonialsGrid.appendChild(testimonialCard);
            });
        })
        .catch(error => console.error('Error fetching testimonials:', error));
});

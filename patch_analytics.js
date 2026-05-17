        function calculateAnalyticsMetrics(items) {
            let totalUnique = items.length;
            let totalStockUnits = 0;
            let totalValuation = 0;
            let lowStockCount = 0;

            let catBookCount = 0;
            let catNotebookCount = 0;
            let catStationeryCount = 0;

            items.forEach(item => {
                const stock = parseInt(item.stock) || 0;
                totalStockUnits += stock;
                
                if (item.category === "Book") catBookCount += stock;
                else if (item.category === "Notebook") catNotebookCount += stock;
                else catStationeryCount += stock;
            });

            document.getElementById("kpiTotalItems").innerText = formatCompactNumber(totalUnique);
            document.getElementById("kpiTotalStock").innerText = formatCompactNumber(totalStockUnits);
            document.getElementById("kpiStockBreakdown").innerText = `Books: ${formatCompactNumber(catBookCount)} | Notebooks: ${formatCompactNumber(catNotebookCount)} | Stat.: ${formatCompactNumber(catStationeryCount)}`;

            // --- Top Trendings Extraction (Based on dynamic items slice or custom key) ---
            const trendingContainer = document.getElementById("kpiTrendingItems");
            if (trendingContainer && items.length > 0) {
                // Sorting strategy for mock display sorting by lowest/highest ratios if transaction metrics aren't fully baked
                const sortedTrending = [...items].slice(0, 2); 
                trendingContainer.innerHTML = sortedTrending.map(i => `<div>🔥 ${i.name}</div>`).join('');
            }

            // --- Recent Added items Extraction ---
            const recentContainer = document.getElementById("kpiRecentItems");
            if (recentContainer && items.length > 0) {
                // Sorted by reverse order assuming latest database auto-increment ID comes last
                const sortedRecent = [...items].sort((a, b) => b.id - a.id).slice(0, 2);
                recentContainer.innerHTML = sortedRecent.map(i => `<div>📦 ${i.name}</div>`).join('');
            }
        }

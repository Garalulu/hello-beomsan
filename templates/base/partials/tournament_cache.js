<script>
// Global Tournament Cache (available on all pages)
if (!window.tournamentCache && localStorage.getItem('tournamentCache')) {
    try {
        const cacheData = JSON.parse(localStorage.getItem('tournamentCache'));
        if (cacheData && (Date.now() - cacheData.timestamp) < 24 * 60 * 60 * 1000) {
            // Create a lightweight cache accessor for non-voting pages
            window.tournamentCache = {
                isResourceCached: function(url, type = 'image') {
                    const preloadedImages = new Set(cacheData.preloadedImages || []);
                    const preloadedAudio = new Set(cacheData.preloadedAudio || []);
                    
                    if (type === 'image') {
                        return preloadedImages.has(url);
                    } else if (type === 'audio') {
                        return preloadedAudio.has(url);
                    }
                    return false;
                },
                getCacheStats: function() {
                    return {
                        images_cached: (cacheData.preloadedImages || []).length,
                        audio_cached: (cacheData.preloadedAudio || []).length,
                        tournament_active: cacheData.isTournamentActive !== false
                    };
                },
                sessionData: cacheData.sessionData
            };
            console.log('🌐 Global cache accessor loaded:', window.tournamentCache.getCacheStats());
        }
    } catch (error) {
        console.warn('Could not load global cache accessor:', error);
    }
}
</script>
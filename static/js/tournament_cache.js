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
                    
                    if (type === 'image') {
                        return preloadedImages.has(url);
                    } else if (type === 'audio') {
                        return false; // Audio caching disabled
                    }
                    return false;
                },
                getCacheStats: function() {
                    return {
                        images_cached: (cacheData.preloadedImages || []).length,
                        tournament_active: cacheData.isTournamentActive !== false
                    };
                },
                preloadAudioForNextMatch: function() {
                    // Audio preloading disabled - Google Drive audio cannot be effectively cached
                    console.log('ℹ️ Audio preloading disabled - using on-demand loading instead');
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
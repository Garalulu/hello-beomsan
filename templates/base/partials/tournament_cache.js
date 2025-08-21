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
                preloadAudioForNextMatch: function() {
                    // Enhanced audio preloading for better performance
                    try {
                        const sessionData = cacheData.sessionData;
                        if (sessionData && Array.isArray(sessionData)) {
                            // Find next potential matches and preload their audio
                            sessionData.slice(0, 4).forEach((song, index) => {
                                if (song.audio_url && song.audio_url.includes('drive.google.com')) {
                                    // Use link preload for Google Drive audio
                                    const link = document.createElement('link');
                                    link.rel = 'preload';
                                    link.as = 'document';
                                    link.href = song.audio_url;
                                    link.setAttribute('data-preload-type', 'audio-next');
                                    
                                    // Add to head if not already there
                                    const existing = document.querySelector(`link[href="${song.audio_url}"]`);
                                    if (!existing) {
                                        document.head.appendChild(link);
                                        console.log('🎵 Preloaded audio for next match:', song.title);
                                    }
                                }
                            });
                        }
                    } catch (error) {
                        console.warn('Audio preloading failed:', error);
                    }
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
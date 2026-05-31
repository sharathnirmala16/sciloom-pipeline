/**
 * Validates whether the given string is a valid GitHub repository URL.
 */
export function validateGitHubUrl(url: string | null | undefined): boolean {
  if (!url) {
    return false;
  }
  // Regular expression to check for valid github repository URLs
  // Must include protocol (http or https), domain, username, and repository name.
  const githubRegex = /^https?:\/\/(www\.)?github\.com\/[a-zA-Z0-9_-]+\/[a-zA-Z0-9_.-]+(?:\.git)?\/?$/;
  
  // Make sure it doesn't end immediately after the slash of the domain, and doesn't match single username
  const cleanUrl = url.trim();
  if (!githubRegex.test(cleanUrl)) {
    return false;
  }
  
  // Exclude root URL paths like github.com/settings, github.com/features, etc.
  const path = cleanUrl.replace(/^https?:\/\/(www\.)?github\.com\//, '').split('/');
  if (path.length < 2 || !path[0] || !path[1] || path[1] === '.git') {
    return false;
  }
  
  return true;
}

/**
 * Parses raw textual input representing claims, splitting by line breaks,
 * cleaning up bullet points and numbers, and filtering out empty entries.
 */
export function parseClaims(rawClaims: string | null | undefined): string[] {
  if (!rawClaims) {
    return [];
  }

  // Split by line break
  const lines = rawClaims.split(/\r?\n/);
  
  return lines
    .map(line => {
      let trimmed = line.trim();
      // Remove leading dashes, asterisks, bullet points or numbers followed by dot/dash
      trimmed = trimmed.replace(/^[-*•]\s*/, ''); // removes -, *, •
      trimmed = trimmed.replace(/^\d+[\s.)-]+\s*/, ''); // removes 1., 1), 1-
      return trimmed.trim();
    })
    .filter(line => line.length > 0);
}

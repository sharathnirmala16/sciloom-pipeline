import { describe, it, expect } from 'vitest';
import { validateGitHubUrl, parseClaims } from './job-validator';

describe('JobValidator Utilities', () => {
  describe('validateGitHubUrl', () => {
    it('should return true for valid GitHub repository URLs', () => {
      expect(validateGitHubUrl('https://github.com/angular/angular')).toBe(true);
      expect(validateGitHubUrl('http://github.com/angular/angular.git')).toBe(true);
      expect(validateGitHubUrl('https://github.com/google-deepmind/sciloom-pipeline')).toBe(true);
    });

    it('should return false for non-GitHub or malformed URLs', () => {
      expect(validateGitHubUrl('https://gitlab.com/angular/angular')).toBe(false);
      expect(validateGitHubUrl('github.com/angular/angular')).toBe(false);
      expect(validateGitHubUrl('https://github.com/')).toBe(false);
      expect(validateGitHubUrl('https://github.com/angular')).toBe(false);
      expect(validateGitHubUrl('')).toBe(false);
      expect(validateGitHubUrl(null)).toBe(false);
      expect(validateGitHubUrl(undefined)).toBe(false);
    });
  });

  describe('parseClaims', () => {
    it('should split raw text into clean claims lists', () => {
      const input = `
        - Claim 1: Accuracy is 95%
        * Claim 2: Training time is under 2 hours
        1. Claim 3: Performance exceeds baseline by 5%
      `;
      const expected = [
        'Claim 1: Accuracy is 95%',
        'Claim 2: Training time is under 2 hours',
        'Claim 3: Performance exceeds baseline by 5%'
      ];
      expect(parseClaims(input)).toEqual(expected);
    });

    it('should handle comma or newline-separated values and filter empty lines', () => {
      const input = '\n  Only one claim here  \n\n\n';
      expect(parseClaims(input)).toEqual(['Only one claim here']);
    });
  });
});
